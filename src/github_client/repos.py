import httpx

GITHUB_API = "https://api.github.com"
_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def _auth_headers(token: str) -> dict:
    return {**_HEADERS, "Authorization": f"Bearer {token}"}


async def list_user_repos(token: str) -> list[dict]:
    """사용자가 접근 가능한 리포 목록 반환 (public + private, per_page=100, sort=updated)."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GITHUB_API}/user/repos",
            params={"per_page": 100, "sort": "updated", "affiliation": "owner,collaborator"},
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        return [
            {
                "full_name": r["full_name"],
                "private": r["private"],
                "description": r.get("description") or "",
            }
            for r in resp.json()
        ]


async def create_webhook(token: str, repo_full_name: str, webhook_url: str, secret: str) -> int:
    """Webhook 생성 → webhook_id 반환."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo_full_name}/hooks",
            json={
                "name": "web",
                "active": True,
                "events": ["push", "pull_request"],
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    "secret": secret,
                    "insecure_ssl": "0",
                },
            },
            headers=_auth_headers(token),
        )
        resp.raise_for_status()
        return resp.json()["id"]


async def delete_webhook(token: str, repo_full_name: str, webhook_id: int) -> bool:
    """Webhook 삭제. 성공(204) 시 True, 그 외 False 반환."""
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{GITHUB_API}/repos/{repo_full_name}/hooks/{webhook_id}",
            headers=_auth_headers(token),
        )
        return resp.status_code == 204
