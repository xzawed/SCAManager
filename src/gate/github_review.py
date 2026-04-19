"""GitHub review and merge API wrappers for the Gate Engine."""
import asyncio
import logging

import httpx

from src.github_client.helpers import github_api_headers

logger = logging.getLogger(__name__)

_MERGEABLE_BLOCK = frozenset({"dirty", "blocked", "behind", "draft"})
_UNKNOWN_RETRY_LIMIT = 3
_UNKNOWN_RETRY_DELAY = 3.0


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
    """HTTP 코드와 GitHub 메시지를 user-facing 한국어 사유로 변환."""
    gh_msg = ""
    try:
        gh_msg = exc.response.json().get("message", "")
    except (ValueError, AttributeError):
        pass
    code = exc.response.status_code
    label = {
        405: "not_mergeable",
        403: "forbidden",
        422: "unprocessable",
        409: "conflict",
    }.get(code, f"http_{code}")
    return f"{label}: {gh_msg or str(exc)}"


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
    # B안: mergeable_state 사전 확인 + unknown 재시도
    state = "unknown"
    for attempt in range(_UNKNOWN_RETRY_LIMIT):
        try:
            state = await get_pr_mergeable_state(github_token, repo_full_name, pr_number)
        except httpx.HTTPError as exc:
            logger.warning("mergeable_state 조회 실패 (pr=%d): %s", pr_number, exc)
            state = "unknown"
        if state != "unknown":
            break
        if attempt < _UNKNOWN_RETRY_LIMIT - 1:
            await asyncio.sleep(_UNKNOWN_RETRY_DELAY)

    if state in _MERGEABLE_BLOCK:
        return (False, f"{state}: 머지 조건 미충족 (충돌·브랜치 보호·드래프트)")
    if state == "unknown":
        return (False, "unknown: GitHub mergeable 계산 완료 실패 — 재시도 필요")

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
        reason = f"network_error: {exc}"
        logger.warning("PR Merge 실패 (repo=%s, pr=%d): %s", repo_full_name, pr_number, reason)
        return (False, reason)
