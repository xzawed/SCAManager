"""Shared helpers for GitHub API client modules."""


def github_api_headers(token: str) -> dict:
    """Return standard GitHub REST API authentication headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
