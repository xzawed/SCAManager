"""GitHub review and merge API wrappers for the Gate Engine."""
import asyncio
import logging

import httpx

from src.config import settings
from src.constants import GITHUB_API
from src.gate import merge_reasons
from src.github_client.helpers import github_api_headers
from src.shared.http_client import get_http_client
from src.shared.log_safety import sanitize_for_log
from src.shared.http_client import HTTPX_SEND_ERRORS

logger = logging.getLogger(__name__)

# Phase F QW1: "unstable" 추가 — BPR "Require status checks" 설정된 repo 에서
# CI 일부 실패 시 mergeable_state=unstable. 이 상태에서 merge 시도하면 405 실패.
_MERGEABLE_BLOCK = frozenset({"dirty", "blocked", "behind", "draft", "unstable"})


class HeadMovedError(Exception):
    """분석 SHA 와 PR head 가 어긋나 리뷰를 붙이지 않고 중단했다 (정상 fail-closed).

    Raised instead of posting when the PR head no longer matches the analyzed SHA.
    """


async def post_github_review(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    decision: str,
    body: str,
    *,
    commit_id: str | None = None,
) -> None:
    """Post an APPROVE or REQUEST_CHANGES review on a GitHub pull request.

    🔴 `commit_id` = 분석된 SHA. 전달 시 **POST 직전 PR head 를 조회해 일치하지 않으면
    `HeadMovedError` 를 던지고 POST 하지 않는다**(fail-closed) → 이동한 head 에 SCAManager 의
    APPROVE 가 붙어 branch protection 의 auto-merge-on-approval 이 **미분석 커밋을 머지**하는
    것을 차단. merge 의 `expected_sha`(#1057)와 목적은 같으나 **강제 주체가 다르다**(아래).
    빈 값/None 은 결속 미적용(하위 호환) — head 조회조차 하지 않는다.

    🔴🔴 **GitHub 은 이 결속을 강제해 주지 않는다 — 실측으로 반증됨 (owed #1072, 2026-07-26)**
    이전 구현은 "구 `commit_id` 를 보내면 GitHub 이 422 로 거부한다"는 전제였으나, 격리 리포
    실측에서 **구 SHA·force-push 로 PR 에서 사라진 SHA 모두 200** 으로 수락됐다(리뷰가 그 SHA 로
    기록됨). 422 는 **저장소에 오브젝트가 아예 없을 때만** 난다(`The commitOID is not part of the
    pull request`). 분석된 SHA 는 정의상 저장소에 존재하므로 그 가드는 **원리적으로 발화 불가**였고,
    실제로 운영 auto-approve 104 건 중 한 번도 차단하지 않았다. 그래서 **우리 코드가** 강제한다.

    🔴 **정직한 한계**: GET(head 조회) → POST 사이에 head 가 또 움직이는 레이스는 남는다.
    리뷰 API 에는 merge 의 `sha` 파라미터 같은 **서버측 원자성 수단이 없음이 실측으로 확인**됐으므로
    이것이 가용 최선이다. 놓친 드리프트는 손실이 아니다 — 새 head 의 synchronize 웹훅이 그 커밋을
    분석해 자체 게이트를 돈다(`_run_auto_merge_retry` 드롭 논리와 동일).

    Raises:
        HeadMovedError: commit_id 가 주어졌는데 현재 head 와 다르거나 head 를 판정할 수 없을 때.
    """
    event = "APPROVE" if decision == "approve" else "REQUEST_CHANGES"
    payload: dict = {"body": body, "event": event}
    if commit_id:
        # 🔴 클라이언트 측 결속 — GitHub 이 막아주지 않으므로 POST 전에 우리가 확인한다.
        # Client-side binding — GitHub does not enforce it, so verify before POSTing.
        _, head_sha = await get_pr_mergeable_state(github_token, repo_full_name, pr_number)
        if head_sha != commit_id:
            # 메시지는 영문 고정 — 운영자용 내부 진단이고, 발신 모듈 한국어 가드의 대상 표면이다.
            # English-only message: internal diagnostic, and this module is scanned by the
            # hardcoded-Korean send-path guard (logger args are exempt, raise arguments are not).
            head_repr = sanitize_for_log(head_sha)[:12] if head_sha else "<undeterminable>"
            raise HeadMovedError(
                f"analyzed={sanitize_for_log(commit_id)[:12]} head={head_repr}"
            )
        payload["commit_id"] = commit_id
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    client = get_http_client()  # 싱글톤
    r = await client.post(
        url,
        json=payload,
        headers=github_api_headers(github_token),
    )
    r.raise_for_status()


async def get_pr_mergeable_state(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
) -> tuple[str, str]:
    """GET pulls/{N} 에서 mergeable_state 와 head SHA 를 함께 반환.
    Returns mergeable_state and head commit SHA from GET pulls/{N}.

    Returns:
        (state, head_sha) — state 는 GitHub mergeable_state 문자열,
        head_sha 는 PR head commit SHA (HEAD 변경 감지용).
        state, head_sha — state is the GitHub mergeable_state string,
        head_sha is the PR head commit SHA (for HEAD change detection).

    실패 시 ('unknown', '') 반환 — raise_for_status 호출.
    Returns ('unknown', '') on failure — calls raise_for_status.
    """
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    client = get_http_client()  # 싱글톤
    r = await client.get(url, headers=github_api_headers(github_token))
    r.raise_for_status()
    data = r.json()
    state = data.get("mergeable_state", "unknown")
    head_sha = data.get("head", {}).get("sha", "")
    return (state, head_sha)


async def get_pr_base_ref(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    fallback: str = "main",
) -> str:
    """PR 의 base 브랜치 이름을 조회한다 — 실패 시 fallback 반환.
    Fetch the base branch ref for a PR — returns fallback on failure.

    F1: BPR Required Status Checks 조회 시 main 하드코딩 대신 PR 실제 base 브랜치
    사용. develop / staging 등 다양한 base 브랜치 환경에서 정확한 BPR 조회 가능.

    F1: replaces hardcoded "main" with actual PR base ref so BPR checks resolve
    correctly for develop/staging/etc. base branches.
    """
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    try:
        client = get_http_client()
        r = await client.get(url, headers=github_api_headers(github_token))
        r.raise_for_status()
        return r.json().get("base", {}).get("ref", fallback) or fallback
    except HTTPX_SEND_ERRORS:
        # 네트워크 / HTTP 오류 시 fallback (이전 동작 유지)
        # Fall back on network/HTTP error (preserves prior behavior).
        return fallback


def _interpret_merge_error(exc: httpx.HTTPStatusError) -> str:
    """HTTP 코드와 GitHub 메시지를 정규 reason tag + user-facing 사유로 변환.

    Phase F QW5: 라벨을 `src/gate/merge_reasons.py` 상수로 중앙집중화.
    """
    gh_msg = ""
    try:
        gh_msg = exc.response.json().get("message", "")
    except (ValueError, AttributeError):
        pass
    reason_tag = merge_reasons.http_status_to_reason(exc.response.status_code)
    return f"{reason_tag}: {gh_msg or str(exc)}"


async def merge_pr(  # pylint: disable=too-many-locals
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    merge_method: str = "squash",
    *,
    expected_sha: str | None = None,
) -> tuple[bool, str | None, str]:
    """Squash-merge a pull request.

    SHA atomicity guard (Phase 12 D1): expected_sha 를 PUT /merge 에 전달 →
    GitHub 이 HEAD 불일치 시 409 반환해 force-push 코드의 의도치 않은 머지 차단.
    SHA atomicity guard (Phase 12 D1): pass expected_sha to PUT /merge →
    GitHub returns 409 on HEAD mismatch, preventing accidental merge of force-pushed code.

    Returns:
        (True, None, head_sha) on success.
        (False, reason, head_sha) on failure.
        head_sha 는 mergeable_state 조회 시점의 PR HEAD SHA.
        head_sha is the PR HEAD SHA observed during mergeable_state check.
    """
    # mergeable_state 사전 확인 + unknown 재시도 (Phase F QW2: settings 로 파라미터 외부화)
    # mergeable_state pre-check + unknown retry (Phase F QW2: settings-externalised params)
    retry_limit = max(1, settings.merge_unknown_retry_limit)
    retry_delay = max(0.0, settings.merge_unknown_retry_delay)
    state = "unknown"
    head_sha = ""
    for attempt in range(retry_limit):
        try:
            state, head_sha = await get_pr_mergeable_state(github_token, repo_full_name, pr_number)
        except HTTPX_SEND_ERRORS as exc:
            logger.warning("mergeable_state 조회 실패 (pr=%d): %s", pr_number, exc)
            state = "unknown"
            head_sha = ""
        if state != "unknown":
            break
        if attempt < retry_limit - 1:
            await asyncio.sleep(retry_delay)

    if state in _MERGEABLE_BLOCK:
        # 사이클 152 Sprint 2 (P1-1): reason 을 정규 태그만 반환 (language-neutral).
        # 하드코딩 한국어 설명 제거 — get_advice 는 태그만 사용, 알림은 advice(i18n)로 안내.
        # Cycle 152 Sprint 2 (P1-1): return reason as the canonical tag only (language-neutral).
        # Korean detail removed — get_advice uses the tag; notifications rely on advice (i18n).
        reason_tag = merge_reasons.mergeable_state_to_reason(state)
        return (False, reason_tag, head_sha)
    if state == "unknown":
        return (False, merge_reasons.UNKNOWN_STATE_TIMEOUT, head_sha)

    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}/merge"
    try:
        client = get_http_client()  # 싱글톤
        # SHA atomicity guard — expected_sha 전달 시 PUT body 에 포함
        # SHA atomicity guard — include expected_sha in PUT body when provided
        # HEAD 변경 시 GitHub 409 반환 — force-push 코드 머지 방지
        # GitHub returns 409 if HEAD changed — prevents merging force-pushed code
        put_body = {"merge_method": merge_method, **({} if expected_sha is None else {"sha": expected_sha})}
        r = await client.put(
            url,
            json=put_body,
            headers=github_api_headers(github_token),
        )
        r.raise_for_status()
        return (True, None, head_sha)
    except httpx.HTTPStatusError as exc:
        reason = _interpret_merge_error(exc)
        logger.warning(
            "PR Merge 실패 (repo=%s, pr=%d): HTTP %d — %s",
            repo_full_name, pr_number, exc.response.status_code, reason,
        )
        return (False, reason, head_sha)
    except HTTPX_SEND_ERRORS as exc:
        reason = f"{merge_reasons.NETWORK_ERROR}: {exc}"
        logger.warning(
            "PR Merge 실패 (repo=%s, pr=%d): %s",
            sanitize_for_log(repo_full_name), pr_number, sanitize_for_log(reason),
        )
        return (False, reason, head_sha)
