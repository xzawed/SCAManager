"""_ReviewCommentAction — PR 에 AI 리뷰 댓글 발송."""
from __future__ import annotations

import logging

import httpx

from src.gate.registry import GateContext, register
from src.notifier.github_comment import post_pr_comment_from_result as post_pr_comment

logger = logging.getLogger(__name__)


class _ReviewCommentAction:
    name = "review_comment"

    def is_enabled(self, ctx: GateContext) -> bool:
        """pr_review_comment=True 이면 실행."""
        return bool(ctx.config.pr_review_comment)

    async def run(self, ctx: GateContext) -> None:
        """PR 에 AI 리뷰 댓글을 발송한다. 실패 시 오류 로그만 기록."""
        try:
            await post_pr_comment(
                github_token=ctx.github_token,
                repo_name=ctx.repo_name,
                pr_number=ctx.pr_number,
                result=ctx.result,
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("PR Review Comment 실패: %s", exc)


register(_ReviewCommentAction())
