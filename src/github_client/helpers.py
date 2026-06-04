"""Shared helpers for GitHub API client modules."""
from urllib.parse import quote


def repo_path(full_name: str) -> str:
    """owner/repo 를 URL 안전하게 인코딩 (슬래시는 유지) — github_client URL 빌드 단일 출처.
    URL-encode owner/repo defensively while preserving the path slash — single source for github_client URL builds.

    GitHub 저장소 이름은 신뢰 입력이지만 방어적 인코딩으로 path injection 을 차단한다.
    GitHub repo names are trusted input, but defensive encoding blocks path injection.
    """
    return quote(full_name, safe="/")


def github_api_headers(token: str) -> dict:
    """Return standard GitHub REST API authentication headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
