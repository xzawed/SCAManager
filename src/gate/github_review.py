"""GitHub review and merge API wrappers for the Gate Engine."""
import asyncio
import logging

import httpx

from src.config import settings
from src.gate import merge_reasons
from src.github_client.helpers import github_api_headers
from src.shared.http_client import get_http_client

logger = logging.getLogger(__name__)

# Phase F QW1: "unstable" 추가 — BPR "Require status checks" 설정된 repo 에서
# CI 일부 실패 시 mergeable_state=unstable. 이 상태에서 merge 시도하면 405 실패.
_MERGEABLE_BLOCK = frozenset({"dirty", "blocked", "behind", "draft", "unstable"})


async def post_github_review(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    decision: str,
    body: str,
) -> None:
    """Post an APPROVE or REQUEST_CHANGES review on a GitHub pull request."""
    event = "APPROVE" if decision == "approve" else "REQUEST_CHANGES"
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    client = get_http_client()  # 싱글톤
    r = await client.post(
        url,
        json={"body": body, "event": event},
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
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
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
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    try:
        client = get_http_client()
        r = await client.get(url, headers=github_api_headers(github_token))
        r.raise_for_status()
        return r.json().get("base", {}).get("ref", fallback) or fallback
    except httpx.HTTPError:
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
        except httpx.HTTPError as exc:
            logger.warning("mergeable_state 조회 실패 (pr=%d): %s", pr_number, exc)
            state = "unknown"
            head_sha = ""
        if state != "unknown":
            break
        if attempt < retry_limit - 1:
            await asyncio.sleep(retry_delay)

    if state in _MERGEABLE_BLOCK:
        reason_tag = merge_reasons.mergeable_state_to_reason(state)
        return (False, f"{reason_tag}: 머지 조건 미충족 (state={state})", head_sha)
    if state == "unknown":
        return (False, f"{merge_reasons.UNKNOWN_STATE_TIMEOUT}: GitHub mergeable 계산 미완료", head_sha)

    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/merge"
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
    except httpx.HTTPError as exc:
        reason = f"{merge_reasons.NETWORK_ERROR}: {exc}"
        logger.warning("PR Merge 실패 (repo=%s, pr=%d): %s", repo_full_name, pr_number, reason)
        return (False, reason, head_sha)
