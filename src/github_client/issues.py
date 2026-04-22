"""GitHub Issues API helpers."""
import httpx

from src.constants import GITHUB_API
from src.github_client.helpers import github_api_headers


async def close_issue(
    token: str,
    repo_full_name: str,
    issue_number: int,
    state_reason: str = "completed",
) -> None:
    """Issue 를 closed 상태로 전환. 실패 시 httpx.HTTPStatusError 전파."""
    url = f"{GITHUB_API}/repos/{repo_full_name}/issues/{issue_number}"
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            url,
            json={"state": "closed", "state_reason": state_reason},
            headers=github_api_headers(token),
        )
        resp.raise_for_status()
