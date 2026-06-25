"""GitHub Issues API helpers."""
from src.constants import GITHUB_API
from src.github_client.helpers import github_api_headers, repo_path
from src.shared.http_client import get_http_client


async def close_issue(
    token: str,
    repo_full_name: str,
    issue_number: int,
    state_reason: str = "completed",
) -> None:
    """Issue 를 closed 상태로 전환. 실패 시 httpx.HTTPStatusError 전파."""
    url = f"{GITHUB_API}/repos/{repo_path(repo_full_name)}/issues/{issue_number}"
    client = get_http_client()  # 싱글톤
    resp = await client.patch(
        url,
        json={"state": "closed", "state_reason": state_reason},
        headers=github_api_headers(token),
    )
    resp.raise_for_status()


async def create_issue(
    token: str,
    repo_full_name: str,
    *,
    title: str,
    body: str,
    labels: list[str],
) -> dict:
    """GitHub Issue 를 생성하고 number·html_url·state 를 반환한다.
    Create a GitHub Issue and return its number, html_url, and state.
    """
    url = f"{GITHUB_API}/repos/{repo_path(repo_full_name)}/issues"
    client = get_http_client()
    resp = await client.post(
        url,
        json={"title": title, "body": body, "labels": labels},
        headers=github_api_headers(token),
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "number": data["number"],
        "html_url": data["html_url"],
        "state": data["state"],
    }


async def get_issue_state(
    token: str,
    repo_full_name: str,
    issue_number: int,
) -> str:
    """GitHub Issue 현재 상태("open" | "closed")를 반환한다.
    Return the current state ("open" | "closed") of a GitHub Issue.
    """
    url = f"{GITHUB_API}/repos/{repo_path(repo_full_name)}/issues/{issue_number}"
    client = get_http_client()
    resp = await client.get(url, headers=github_api_headers(token))
    resp.raise_for_status()
    return resp.json()["state"]
