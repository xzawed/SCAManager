"""GitHub Check Runs / Status API — Phase 12 CI 상태 조회.
GitHub Check Runs / Status API — Phase 12 CI status queries.
"""
import logging
import time
from urllib.parse import quote

import httpx

from src.constants import GITHUB_API
from src.github_client.helpers import repo_path
from src.shared.http_client import get_http_client
from src.shared.log_safety import sanitize_for_log
from src.shared.http_client import HTTPX_SEND_ERRORS

logger = logging.getLogger(__name__)

# ── 모듈 레벨 상수 ────────────────────────────────────────────────────────
# ── Module-level constants ────────────────────────────────────────────────

# 페이지네이션 최대 페이지 수 / Maximum pages for check-run pagination
_MAX_PAGES = 5

# 성공으로 간주하는 conclusion 값 / Conclusion values treated as success
_SUCCESS_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})

# 실패로 간주하는 conclusion 값 / Conclusion values treated as failure
_FAILURE_CONCLUSIONS = frozenset({"failure", "cancelled", "timed_out", "action_required"})

# GitHub API 공통 헤더 / Common GitHub API headers
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

# ── 필수 체크 컨텍스트 캐시 (5분 TTL) ───────────────────────────────────
# ── Required check contexts cache (5-minute TTL) ─────────────────────────
# (repo_full_name, branch) → (contexts_set, cached_at_timestamp)
_required_contexts_cache: dict[tuple[str, str], tuple[set[str], float]] = {}

# 🔴 실패 쿨다운 — 성공 캐시와 **분리한다.**
#
# 실패를 성공 캐시에 넣으면 일시 장애가 TTL 동안 «필수 체크 없음» 으로 굳는다(감사 A5).
# 그래서 캐시하지 않기로 했는데, 그 순간 새 위험이 생긴다: 429 를 받고도 다음 호출이
# 곧바로 GitHub 을 다시 때린다 — **이미 rate limit 인데 계속 두드리는** 꼴이다
# (Grok 지적, session 01a03ceb). 이전엔 5분 캐시가 우연히 쿨다운 노릇을 했다.
#
# 쿨다운은 «답» 이 아니라 «잠시 묻지 않는다» 이므로 값을 저장하지 않는다.
# 쿨다운 중에는 빈 set 을 그대로 돌려주되(호출부 계약 유지) 요청은 보내지 않는다.
# Separate failure cooldown: never store the failure, just stop asking for a while.
_required_contexts_cooldown: dict[tuple[str, str], float] = {}
_COOLDOWN_RATE_LIMIT = 60.0   # 429 — Retry-After 가 없을 때
_COOLDOWN_AUTH = 30.0         # 401/403 — 토큰 문제는 사람이 고쳐야 한다
_COOLDOWN_MAX = 300.0         # Retry-After 를 그대로 믿지 않는다
_REQUIRED_CONTEXTS_TTL = 300  # seconds
# 🔴 엔트리 상한 (종합감사 P2, services.md 메모리 캐시 상한 규약) — 상한 없이 (repo, branch) 쌍마다
#   무한 누적하면 프로세스 수명 동안 메모리가 단조 증가한다(TTL 은 신선도만 관리·삭제 안 함).
#   webhook/_helpers._store_secret 미러 — 상한 초과 시 만료분 정리 → 그래도 상한이면 최고령 1건 evict.
# Entry cap (mirrors _store_secret): without it, each (repo, branch) accumulates for the process
#   lifetime since TTL only governs freshness, not deletion.
_REQUIRED_CONTEXTS_CACHE_MAX = 2048


def _store_required_contexts(cache_key: tuple[str, str], contexts: set[str], now: float) -> None:
    """필수 컨텍스트 캐시에 저장하되 엔트리 상한을 강제한다.
    Store into the required-contexts cache while enforcing the entry cap.

    상한 초과 시: (1) 만료된 엔트리 정리 → (2) 여전히 상한이면 가장 오래된(=최고령) 1건 evict.
    On overflow: purge expired entries, then evict the oldest cached one if still at the cap.
    """
    if (len(_required_contexts_cache) >= _REQUIRED_CONTEXTS_CACHE_MAX
            and cache_key not in _required_contexts_cache):
        for key in [k for k, (_, at) in _required_contexts_cache.items()
                    if now - at >= _REQUIRED_CONTEXTS_TTL]:
            del _required_contexts_cache[key]
        if len(_required_contexts_cache) >= _REQUIRED_CONTEXTS_CACHE_MAX:
            oldest = min(_required_contexts_cache, key=lambda k: _required_contexts_cache[k][1])
            del _required_contexts_cache[oldest]
    _required_contexts_cache[cache_key] = (contexts, now)


def _auth_headers(token: str) -> dict:
    """Authorization 헤더를 포함한 요청 헤더 반환.
    Returns request headers including the Authorization header.
    """
    return {**_HEADERS, "Authorization": f"Bearer {token}"}


async def get_ci_status(
    token: str,
    repo_full_name: str,
    commit_sha: str,
    *,
    required_contexts: set[str] | None = None,
) -> str:
    """커밋 SHA의 CI 상태를 반환한다: 'running'|'passed'|'failed'|'unknown'.
    Returns CI status for a commit SHA: 'running'|'passed'|'failed'|'unknown'.

    required_contexts:
    - None → 모든 체크 고려 / consider ALL checks
    - set (비어 있어도) → 해당 이름의 체크만 고려 / only consider checks in the set
    - 빈 set → BPR Required Status Checks 미설정 → None 으로 fallback 후 모든 체크 고려
      Empty set → no required status checks under BPR → fall back to None (consider all checks)
      (이전 동작은 즉시 'failed' 였으나, BPR 미설정 Repo 가 일반적이고 그 경우 사용자
       의도는 "informational 체크의 진행 상태로 판단" 이므로 fallback 으로 변경)
    """
    # 빈 set: BPR Required Status Checks 미설정 → 모든 체크 고려 fallback
    # Empty set: no required status checks under BPR → fall back to considering all checks
    if required_contexts is not None and len(required_contexts) == 0:
        logger.debug(
            "required_contexts는 빈 set — BPR Required 미설정, 모든 체크 고려 fallback (%s %s)"
            " / required_contexts is empty set — no BPR required checks, falling back to all checks (%s %s)",
            sanitize_for_log(repo_full_name), sanitize_for_log(commit_sha),
            sanitize_for_log(repo_full_name), sanitize_for_log(commit_sha),
        )
        required_contexts = None

    client = get_http_client()

    # ── 1. Check Runs API 페이지네이션 수집 ───────────────────────────
    # ── 1. Collect check runs via paginated API ────────────────────────
    all_check_runs: list[dict] = []
    base_url = (
        f"{GITHUB_API}/repos/{repo_path(repo_full_name)}/commits/{quote(commit_sha, safe='')}/check-runs"
    )

    for page_num in range(1, _MAX_PAGES + 1):
        # 🔴 **서버가 준 URL 을 요청하지 않는다.** `Link` 헤더의 next URL 을 그대로
        #   따라가면 그 요청에 `Authorization: Bearer <토큰>` 이 실리고, 응답이 변조되면
        #   토큰이 임의 호스트로 나간다 (#1515). origin 검증은 CodeQL 이 sanitizer 로
        #   인식하지 않았다(#1514 에서 4회 실패) — **taint 를 아예 없애는 것**이 답이다:
        #   URL 은 우리가 만들고(`base` + 정수 `page`), 서버에게서는 「더 있는가」라는
        #   **신호만** 받는다. 형제 `repos.py::list_webhooks` 와 같은 계약이다.
        # Never request a server-supplied URL: build it ourselves and read only the
        # has-more signal from the Link header. Removes the taint instead of sanitizing it.
        resp = await client.get(
            base_url, params={"page": page_num}, headers=_auth_headers(token))
        resp.raise_for_status()
        data = resp.json()
        all_check_runs.extend(data.get("check_runs", []))

        # 다음 페이지 유무는 서버가 안다 — 그 **불리언**만 쓴다(URL 은 안 쓴다).
        # Use only the boolean; never the URL.
        if not resp.links.get("next"):
            break
    else:
        # 🔴 `_MAX_PAGES` 를 다 쓰고도 다음 페이지가 남았다 = 결과 불확실.
        #   여기서는 던지지 않고 `unknown` 을 낸다 — 게이트 계약상 unknown 이 이미
        #   「판정 보류」이고, 부분 목록으로 `passed` 를 내는 것보다 정직하다.
        #   (형제 `list_webhooks` 가 던지는 이유는 그쪽 호출부가 목록을 「전부」라고
        #    믿고 삭제하기 때문이다 — 여기는 판정만 한다.)
        # Exhausted the cap with more pages left: uncertain, so 'unknown' (the gate's
        # existing hold verdict) rather than a verdict from a partial list.
        logger.warning(
            "체크런 페이지 %d 초과 — 결과 불확실, 'unknown' 반환 (%s %s)"
            " / check-run page count exceeded %d — returning 'unknown' (%s %s)",
            _MAX_PAGES, sanitize_for_log(repo_full_name), sanitize_for_log(commit_sha),
            _MAX_PAGES, sanitize_for_log(repo_full_name), sanitize_for_log(commit_sha),
        )
        return "unknown"

    # ── 2. 필터링 적용 ────────────────────────────────────────────────
    # ── 2. Apply required_contexts filter ─────────────────────────────
    if required_contexts is not None:
        # Non-empty set: 필수 체크 이름만 고려 / non-empty set: only consider required names
        filtered = [r for r in all_check_runs if r.get("name") in required_contexts]
    else:
        # None: 모든 체크 고려 / None: consider all checks
        filtered = all_check_runs

    # ── 3. Check Runs 결과 분류 ────────────────────────────────────────
    # ── 3. Classify check run results ─────────────────────────────────
    if filtered:
        return _classify_check_runs(filtered)

    # ── 4. 레거시 Commit Status fallback ─────────────────────────────
    # ── 4. Legacy Commit Status fallback ──────────────────────────────
    legacy_resp = await client.get(
        f"{GITHUB_API}/repos/{repo_path(repo_full_name)}/commits/{quote(commit_sha, safe='')}/status",
        headers=_auth_headers(token),
    )
    legacy_resp.raise_for_status()
    legacy_data = legacy_resp.json()

    statuses = legacy_data.get("statuses", [])
    if not statuses:
        return "unknown"

    # 🔴 required_contexts 필터 (종합감사 P1-9) — 레거시 Commit Status fallback 도 Check Runs 와
    #   동일하게 **필수 컨텍스트만** 고려한다. 집계 `state` 는 비-필수 status(coverage/coveralls 등)의
    #   실패까지 반영하므로, 필수 체크(jenkins/build 등)는 통과했는데 비-필수가 실패하면 mergeable
    #   PR 이 UNSTABLE_CI → 재시도 → terminal 로 오abandon 된다.
    # Legacy fallback must honor required_contexts too: the aggregate `state` folds in non-required
    #   status failures, so a passing required check + failing non-required one abandons a mergeable PR.
    if required_contexts:
        return _legacy_required_ci_status(statuses, required_contexts)

    state = legacy_data.get("state", "")
    return _legacy_state_to_ci_status(state)


def _legacy_required_ci_status(statuses: list[dict], required_contexts: set[str]) -> str:
    """필수 컨텍스트로 필터한 개별 commit status 에서 CI 상태 판별 — 집계 state 대신 사용.

    Classify CI status from the required-context subset of individual commit statuses,
    not the aggregate `state`. 필수 status 미도착 = 'running'(미확정, terminal 오판 방지).
    """
    required = [s for s in statuses if s.get("context") in required_contexts]
    if not required:
        return "running"  # 필수 컨텍스트 status 가 아직 안 나타남 → 미확정
    states = [s.get("state", "") for s in required]
    if any(st == "pending" for st in states):
        return "running"
    if all(st == "success" for st in states):
        return "passed"
    return "failed"


def _classify_check_runs(check_runs: list[dict]) -> str:
    """체크런 목록에서 CI 상태를 판별한다.
    Determines CI status from a list of check runs.
    """
    for run in check_runs:
        status = run.get("status", "")
        # 진행 중 또는 대기 중 → 'running' / In-progress or queued → 'running'
        # GitHub API 반환 가능 상태: in_progress, queued, waiting, pending, requested
        # All non-completed GitHub check statuses: in_progress, queued, waiting, pending, requested
        if status in ("in_progress", "queued", "waiting", "pending", "requested"):
            return "running"

    # 모두 completed — conclusion 확인 / All completed — check conclusions
    # 성공 집합에 없는 conclusion은 실패/미확인으로 처리 (안전 기본값)
    # Conclusions not in the success set are treated as failure/unknown (safe default)
    for run in check_runs:
        conclusion = run.get("conclusion") or ""
        if conclusion not in _SUCCESS_CONCLUSIONS:
            return "failed"

    return "passed"


def _legacy_state_to_ci_status(state: str) -> str:
    """레거시 commit status state를 CI 상태로 변환.
    Converts legacy commit status state to CI status string.
    """
    if state == "pending":
        return "running"
    if state == "success":
        return "passed"
    if state in ("failure", "error"):
        return "failed"
    return "unknown"


def _classify_bpr_http_error(
    exc: httpx.HTTPStatusError,
    repo_full_name: str,
    branch: str,
) -> tuple[set[str], bool, float]:
    """BPR 조회 HTTP 오류를 분류해 `(빈 set, 캐시해도 되는가)` 를 돌려준다.

    - 404: **정상** — BPR 미설정. debug 로그. 캐시한다(안 하면 매 요청마다 GitHub 을 때린다).
    - 401/403: 토큰 권한 부족. warning. **캐시하지 않는다.**
    - 429: GitHub rate limit. warning. **캐시하지 않는다.**
    - 그 외: 예상치 못한 응답. error. **캐시하지 않는다.**

    🔴 반환값이 tuple 인 이유: 빈 set 은 «필수 체크 없음» 과 «조회 실패» 두 가지를
    뜻하는데, 호출부는 그것을 구분하지 못한다(그래서 반환 계약은 그대로 둔다).
    구분이 필요한 곳은 **캐시** 다 — 실패를 5분 굳히면 그동안 머지 판정이 실제와
    다른 근거로 내려진다 (감사 A5, #1519 실측).

    Returns (empty set, cacheable, cooldown_seconds). The empty set means both
    "no required checks" and "lookup failed"; only the cache needs to tell them apart.
    cooldown_seconds > 0 means "stop asking for a while" (never a stored answer).
    """
    code = exc.response.status_code
    safe_repo = sanitize_for_log(repo_full_name)
    safe_branch = sanitize_for_log(branch)
    cacheable = code == 404  # 404 만 «상태» 다. 나머지는 «장애» 이므로 굳히지 않는다.
    cooldown = 0.0
    if code == 404:
        # 가장 흔한 정상 경로 — BPR 자체가 없거나 Required Status Checks 미설정
        # Most common normal case — no BPR or no Required Status Checks
        logger.debug(
            "BPR 미설정 (404) — 빈 set 반환 (%s/%s)"
            " / no BPR configured (404) — returning empty set",
            safe_repo, safe_branch,
        )
    elif code in (401, 403):
        logger.warning(
            "BPR 조회 권한 부족 (HTTP %d) — 토큰 점검 필요 (%s/%s)"
            " / BPR fetch unauthorized — token review needed",
            code, safe_repo, safe_branch,
        )
        cooldown = _COOLDOWN_AUTH
    elif code == 429:
        logger.warning(
            "BPR 조회 rate limit (HTTP 429) — 빈 set 반환, 쿨다운 후 재조회 (%s/%s)"
            " / BPR fetch rate-limited — returning empty set, retried after cooldown",
            safe_repo, safe_branch,
        )
        # GitHub 이 `Retry-After` 를 주면 그것을 쓰되 상한을 건다 — 값을 그대로 믿지 않는다.
        # Honour Retry-After but cap it; never trust the value verbatim.
        cooldown = _COOLDOWN_RATE_LIMIT
        raw_retry = exc.response.headers.get("retry-after")
        if raw_retry:
            try:
                cooldown = min(max(float(raw_retry), 0.0), _COOLDOWN_MAX)
            except ValueError:
                # 비정형 Retry-After — 기본 쿨다운을 그대로 쓴다. 조용히 넘기지 않고
                # 남긴다: 벤더가 형식을 바꾸면 여기가 유일한 관측면이다.
                # Malformed Retry-After: keep the default cooldown, but say so.
                logger.warning(
                    "BPR 429 의 Retry-After 를 읽지 못했다 (%r) — 기본 쿨다운 %.0fs 사용"
                    " / unparsable Retry-After; using the default cooldown",
                    raw_retry[:32], cooldown,
                )
    else:
        logger.error(
            "BPR 조회 HTTP 오류 (HTTP %d) — 예상치 못한 응답 (%s/%s)"
            " / BPR fetch unexpected HTTP status",
            code, safe_repo, safe_branch,
        )
    return set(), cacheable, cooldown


async def get_required_check_contexts(
    token: str,
    repo_full_name: str,
    branch: str,
) -> set[str]:
    """브랜치 보호 필수 체크 컨텍스트 목록 (5분 TTL 캐시).
    Branch protection required check contexts with 5-minute TTL cache.

    Returns empty set if:
    - Branch has no protection rules
    - Branch has no required status checks
    - GitHub returns 404 (no branch protection)

    Callers must treat empty set as "no required checks" → CI state is terminal.
    """
    cache_key = (repo_full_name, branch)
    now = time.monotonic()

    # 캐시 적중 확인 (TTL 내) / Check cache hit within TTL
    if cache_key in _required_contexts_cache:
        cached_set, cached_at = _required_contexts_cache[cache_key]
        if now - cached_at < _REQUIRED_CONTEXTS_TTL:
            return cached_set

    # 🔴 실패 쿨다운 — 값을 돌려주는 게 아니라 **묻지 않는다.**
    # 이미 rate limit 인데 매 호출마다 다시 때리면 상황을 악화시킨다.
    # Cooldown after a failure: do not ask again yet (this is not a cached answer).
    until = _required_contexts_cooldown.get(cache_key)
    if until is not None:
        if now < until:
            return set()
        del _required_contexts_cooldown[cache_key]

    client = get_http_client()

    try:
        resp = await client.get(
            # branch 는 슬래시 포함 가능(feature/x) → safe='/' 로 슬래시 보존 (GitHub path 정합)
            # branch may contain slashes (feature/x) → safe='/' preserves them (GitHub path semantics)
            f"{GITHUB_API}/repos/{repo_path(repo_full_name)}/branches/{quote(branch, safe='/')}"
            f"/protection/required_status_checks",
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        data = resp.json()
        contexts: set[str] = set(data.get("contexts") or [])
        cacheable, cooldown = True, 0.0
    except httpx.HTTPStatusError as exc:
        # HTTP 오류 분류 — 운영 진단을 위해 로그 레벨 분리
        # Classify HTTP error — separate log levels for ops diagnostics
        contexts, cacheable, cooldown = _classify_bpr_http_error(exc, repo_full_name, branch)
    except HTTPX_SEND_ERRORS as exc:
        # 네트워크/연결 오류 (DNS, timeout, ConnectError 등) — **캐시하지 않는다.**
        # Network/connection error — never cached.
        logger.warning(
            "BPR 조회 네트워크 오류 (%s) — 빈 set 반환 (%s/%s)"
            " / BPR fetch network error — returning empty set",
            type(exc).__name__,
            sanitize_for_log(repo_full_name), sanitize_for_log(branch),
        )
        contexts, cacheable, cooldown = set(), False, _COOLDOWN_RATE_LIMIT

    # 🔴 **실패는 캐시하지 않는다.** 빈 set 은 «필수 체크 없음» 과 «조회 실패» 를 함께
    # 뜻하는데, 캐시에 넣으면 일시 장애 한 번이 TTL(5분) 동안 «필수 체크 없음» 으로
    # 굳는다. 그 사이 호출부는 그것을 `None` 으로 바꿔 «모든 체크 고려» 로 넘어가고,
    # 머지 판정이 실제와 다른 근거로 내려진다 (감사 A5, #1519 실측).
    # 기존에 캐시된 **정상** 값이 있으면 그대로 둔다 — 실패가 그것을 밀어내면 안 된다.
    # Never cache a failure; a good cached value must survive a transient error.
    if cacheable:
        _store_required_contexts(cache_key, contexts, now)
    elif cooldown > 0:
        _required_contexts_cooldown[cache_key] = now + cooldown
    return contexts
