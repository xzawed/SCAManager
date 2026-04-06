import logging

import httpx

logger = logging.getLogger(__name__)


async def post_github_review(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    decision: str,
    body: str,
) -> None:
    event = "APPROVE" if decision == "approve" else "REQUEST_CHANGES"
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"body": body, "event": event}, headers=headers)
        r.raise_for_status()


async def merge_pr(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    merge_method: str = "squash",
) -> bool:
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/merge"
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.put(url, json={"merge_method": merge_method}, headers=headers)
            r.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("PR Merge 실패 (repo=%s, pr=%d): %s", repo_full_name, pr_number, exc)
        return False
