"""GitHub review and merge API wrappers for the Gate Engine."""
import asyncio
import logging

import httpx

from src.config import settings
from src.gate import merge_reasons
from src.github_client.helpers import github_api_headers

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
    async with httpx.AsyncClient() as client:
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
) -> str:
    """GET pulls/{N} 에서 mergeable_state 조회. 실패 시 'unknown' 반환."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=github_api_headers(github_token))
        r.raise_for_status()
        return r.json().get("mergeable_state", "unknown")


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


async def merge_pr(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    merge_method: str = "squash",
) -> tuple[bool, str | None]:
    """Squash-merge a pull request.

    Returns:
        (True, None) on success.
        (False, reason) on failure — reason 은 user-facing 사유 문자열.
    """
    # mergeable_state 사전 확인 + unknown 재시도 (Phase F QW2: settings 로 파라미터 외부화)
    retry_limit = max(1, settings.merge_unknown_retry_limit)
    retry_delay = max(0.0, settings.merge_unknown_retry_delay)
    state = "unknown"
    for attempt in range(retry_limit):
        try:
            state = await get_pr_mergeable_state(github_token, repo_full_name, pr_number)
        except httpx.HTTPError as exc:
            logger.warning("mergeable_state 조회 실패 (pr=%d): %s", pr_number, exc)
            state = "unknown"
        if state != "unknown":
            break
        if attempt < retry_limit - 1:
            await asyncio.sleep(retry_delay)

    if state in _MERGEABLE_BLOCK:
        reason_tag = merge_reasons.mergeable_state_to_reason(state)
        return (False, f"{reason_tag}: 머지 조건 미충족 (state={state})")
    if state == "unknown":
        return (False, f"{merge_reasons.UNKNOWN_STATE_TIMEOUT}: GitHub mergeable 계산 미완료")

    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/merge"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                url,
                json={"merge_method": merge_method},
                headers=github_api_headers(github_token),
            )
            r.raise_for_status()
            return (True, None)
    except httpx.HTTPStatusError as exc:
        reason = _interpret_merge_error(exc)
        logger.warning(
            "PR Merge 실패 (repo=%s, pr=%d): HTTP %d — %s",
            repo_full_name, pr_number, exc.response.status_code, reason,
        )
        return (False, reason)
    except httpx.HTTPError as exc:
        reason = f"{merge_reasons.NETWORK_ERROR}: {exc}"
        logger.warning("PR Merge 실패 (repo=%s, pr=%d): %s", repo_full_name, pr_number, reason)
        return (False, reason)
