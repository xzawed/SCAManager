"""ReviewCommentAction — PR에 AI 리뷰 댓글을 게시하는 Gate 액션.
ReviewCommentAction — posts AI review comment to PR.

Sprint E-final: 구현이 이 모듈에 직접 포함됨 (engine.py 위임 제거).
Sprint E-final: Implementation lives here directly (delegation to engine.py removed).
"""
import logging

import httpx

from src.database import SessionLocal
from src.gate.actions import GateAction, GateContext, register
from src.notifier.github_comment import post_pr_comment_from_result as post_pr_comment
from src.notifier._language import resolve_notification_language

logger = logging.getLogger(__name__)


class ReviewCommentAction(GateAction):
    """PR Review Comment Gate 옵션.
    Posts a detailed AI review comment to the PR when pr_review_comment=True.

    P0-H: 독립 SessionLocal() 사용 — asyncio.gather 병렬 실행 시 Session 공유 금지.
    P0-H: Uses independent SessionLocal() — do not share with gather siblings.
    """

    def is_applicable(self, config) -> bool:
        """pr_review_comment=True일 때만 실행."""
        return bool(config.pr_review_comment)

    async def execute(self, ctx: GateContext) -> None:
        """PR에 AI 리뷰 댓글을 게시한다.
        Posts AI review comment to PR.
        """
        if not ctx.config.pr_review_comment:
            return
        try:
            # Phase 3 PR-11 — 3-layer 사용자 언어 결정
            # Phase 3 PR-11 — 3-layer language resolve
            with SessionLocal() as db:
                language = resolve_notification_language(db, config=ctx.config)
            await post_pr_comment(
                github_token=ctx.github_token,
                repo_name=ctx.repo_name,
                pr_number=ctx.pr_number,
                result=ctx.result,
                language=language,
            )
        except (httpx.HTTPError, KeyError) as exc:
            # 예외 타입만 기록 — exc 본문에 HTTP 응답 바디가 포함될 수 있음
            # Log only the exception type — exc body may contain HTTP response details.
            logger.error("PR Review Comment 실패: %s", type(exc).__name__)


register(ReviewCommentAction())
