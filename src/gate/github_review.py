"""GitHub review and merge API wrappers for the Gate Engine."""
import logging

import httpx

from src.github_client.helpers import github_api_headers

logger = logging.getLogger(__name__)


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


async def merge_pr(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    merge_method: str = "squash",
) -> bool:
    """Squash-merge a pull request; returns False on failure without raising."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/merge"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(
                url,
                json={"merge_method": merge_method},
                headers=github_api_headers(github_token),
            )
            r.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("PR Merge 실패 (repo=%s, pr=%d): %s", repo_full_name, pr_number, exc)
        return False
