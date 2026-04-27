"""GitHub Check Runs / Status API — Phase 12 CI 상태 조회.
GitHub Check Runs / Status API — Phase 12 CI status queries.
"""
import logging
import re
import time

from src.constants import GITHUB_API
from src.shared.http_client import get_http_client
from src.shared.log_safety import sanitize_for_log

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
_REQUIRED_CONTEXTS_TTL = 300  # seconds


def _auth_headers(token: str) -> dict:
    """Authorization 헤더를 포함한 요청 헤더 반환.
    Returns request headers including the Authorization header.
    """
    return {**_HEADERS, "Authorization": f"Bearer {token}"}


def _parse_link_next(link_header: str | None) -> str | None:
    """Link 헤더에서 rel="next" URL을 추출한다.
    Extracts rel="next" URL from a Link header.

    Example: '<https://api.github.com/...?page=2>; rel="next", ...' → 'https://...'
    """
    if link_header is None:
        return None
    # rel="next" 세그먼트에서 URL 추출 / Extract URL from rel="next" segment
    match = re.search(r'<([^>]+)>\s*;\s*rel=["\']next["\']', link_header)
    if match:
        return match.group(1)
    return None


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
    url: str | None = (
        f"{GITHUB_API}/repos/{repo_full_name}/commits/{commit_sha}/check-runs"
    )
    page_count = 0

    while url is not None:
        page_count += 1
        if page_count > _MAX_PAGES:
            # 5페이지 초과 → 결과 불확실 / More than 5 pages → uncertain result
            logger.warning(
                "체크런 페이지 %d 초과 — 결과 불확실, 'unknown' 반환 (%s %s)"
                " / check-run page count exceeded %d — returning 'unknown' (%s %s)",
                _MAX_PAGES, sanitize_for_log(repo_full_name), sanitize_for_log(commit_sha),
                _MAX_PAGES, sanitize_for_log(repo_full_name), sanitize_for_log(commit_sha),
            )
            return "unknown"

        resp = await client.get(url, headers=_auth_headers(token))
        resp.raise_for_status()
        data = resp.json()
        all_check_runs.extend(data.get("check_runs", []))

        # Link 헤더에서 다음 페이지 URL 추출 / Extract next page URL from Link header
        url = _parse_link_next(resp.headers.get("Link"))

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
        f"{GITHUB_API}/repos/{repo_full_name}/commits/{commit_sha}/status",
        headers=_auth_headers(token),
    )
    legacy_resp.raise_for_status()
    legacy_data = legacy_resp.json()

    statuses = legacy_data.get("statuses", [])
    if not statuses:
        return "unknown"

    state = legacy_data.get("state", "")
    return _legacy_state_to_ci_status(state)


def _classify_check_runs(check_runs: list[dict]) -> str:
    """체크런 목록에서 CI 상태를 판별한다.
    Determines CI status from a list of check runs.
    """
    for run in check_runs:
        status = run.get("status", "")
        # 진행 중 또는 대기 중 → 'running' / In-progress or queued → 'running'
        if status in ("in_progress", "queued"):
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

    client = get_http_client()

    try:
        resp = await client.get(
            f"{GITHUB_API}/repos/{repo_full_name}/branches/{branch}"
            f"/protection/required_status_checks",
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        data = resp.json()
        contexts: set[str] = set(data.get("contexts") or [])
    except Exception:  # pylint: disable=broad-except
        # 404 또는 기타 오류: 브랜치 보호 없음 / 404 or other error: no branch protection
        contexts = set()

    # 결과 캐시 저장 / Store result in cache
    _required_contexts_cache[cache_key] = (contexts, now)
    return contexts
