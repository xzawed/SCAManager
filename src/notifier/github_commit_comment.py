"""GitHub Commit Comment 자동 게시 — Push 커밋에 AI 리뷰 댓글 첨부."""
import logging

import httpx

from src.github_client.helpers import github_api_headers
from src.notifier.github_comment import _build_comment_from_result

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


async def post_commit_comment(
    *,
    github_token: str,
    repo_name: str,
    commit_sha: str,
    result: dict,
) -> None:
    """Push 커밋에 분석 결과 Comment를 게시한다.

    HTTPError 발생 시 로깅 후 조용히 반환 — 파이프라인을 중단하지 않는다.
    """
    body = _build_comment_from_result(result)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{repo_name}/commits/{commit_sha}/comments",
                json={"body": body},
                headers=github_api_headers(github_token),
            )
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("post_commit_comment 실패 (%s@%s): %s", repo_name, commit_sha, exc)
