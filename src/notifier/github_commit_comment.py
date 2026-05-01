"""GitHub Commit Comment 자동 게시 — Push 커밋에 AI 리뷰 댓글 첨부."""
import logging

import httpx

from src.constants import GITHUB_API
from src.github_client.helpers import github_api_headers
from src.notifier.github_comment import _build_comment_from_result
from src.shared.http_client import get_http_client
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)


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
        client = get_http_client()
        resp = await client.post(
            f"{GITHUB_API}/repos/{repo_name}/commits/{commit_sha}/comments",
            json={"body": body},
            headers=github_api_headers(github_token),
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning(
            "post_commit_comment 실패 (%s@%s): %s",
            sanitize_for_log(repo_name), sanitize_for_log(commit_sha), exc,
        )


# ---------------------------------------------------------------------------
# Notifier Protocol 구현체 (Phase S.3-E) — pipeline.py 에서 이관
# ---------------------------------------------------------------------------
from src.notifier.registry import NotifyContext, register  # noqa: E402  pylint: disable=wrong-import-position


class _CommitCommentNotifier:
    """GitHub Commit Comment 채널 — push 이벤트 전용 (pr_number is None)."""

    name = "commit_comment"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        """채널 활성화 여부를 반환한다."""
        return bool(
            ctx.config and ctx.config.commit_comment
            and ctx.pr_number is None
            and ctx.result_dict
        )

    async def send(self, ctx: NotifyContext) -> None:
        """알림을 전송한다."""
        await post_commit_comment(
            github_token=ctx.owner_token,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            result=ctx.result_dict,
        )


register(_CommitCommentNotifier())
