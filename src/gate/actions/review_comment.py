"""ReviewCommentAction — PR에 AI 리뷰 댓글을 게시하는 Gate 액션.
ReviewCommentAction — posts AI review comment to PR.

구현은 engine.py의 _run_review_comment()에 위임한다.
테스트는 src.gate.engine.post_pr_comment 등 engine 네임스페이스로 패치 가능.
Delegates to engine.py's _run_review_comment(). Tests can patch engine namespace symbols.
"""
import logging

from src.gate.actions import GateAction, GateContext, register

logger = logging.getLogger(__name__)


class ReviewCommentAction(GateAction):
    """PR Review Comment Gate 옵션.
    Posts a detailed AI review comment to the PR when pr_review_comment=True.

    P0-H: 실제 구현(_run_review_comment)이 독립 SessionLocal()을 사용.
    P0-H: Actual impl (_run_review_comment) opens its own SessionLocal().
    """

    def is_applicable(self, config) -> bool:
        """pr_review_comment=True일 때만 실행."""
        return bool(config.pr_review_comment)

    async def execute(self, ctx: GateContext) -> None:
        """engine.py의 _run_review_comment에 위임한다.
        Delegates to engine.py's _run_review_comment.
        """
        # 지연 import — engine.py ↔ actions/ 순환 import 방지
        # Lazy import to avoid circular import between engine.py and actions/
        from src.gate import engine  # pylint: disable=import-outside-toplevel
        await engine._run_review_comment(  # pylint: disable=protected-access
            ctx.config, ctx.github_token, ctx.repo_name, ctx.pr_number, ctx.result,
        )


register(ReviewCommentAction())
