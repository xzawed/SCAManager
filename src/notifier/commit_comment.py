"""Commit-level AI review comment notifier.

GitHub `POST /repos/{owner}/{repo}/commits/{sha}/comments` 엔드포인트로
분석 결과를 커밋 뷰에 직접 남긴다. PR 리뷰 댓글(`github_comment.py`)과
동일한 본문 포맷(`_build_comment_from_result`)을 재사용한다.
"""
import httpx

from src.github_client.helpers import github_api_headers
from src.notifier.github_comment import _build_comment_from_result


async def post_commit_comment_from_result(
    *,
    github_token: str,
    repo_name: str,
    commit_sha: str,
    result: dict,
) -> None:
    """Post a formatted analysis result comment on a GitHub commit."""
    body = _build_comment_from_result(result)
    url = f"https://api.github.com/repos/{repo_name}/commits/{commit_sha}/comments"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            json={"body": body},
            headers=github_api_headers(github_token),
        )
        r.raise_for_status()
