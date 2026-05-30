"""ApproveAction — score 기반 GitHub Approve/Reject 또는 Telegram 반자동 요청 Gate 액션.
ApproveAction — approves/rejects PRs via GitHub review or sends Telegram semi-auto request.

구현은 engine.py의 _run_approve_decision()에 위임한다.
테스트는 src.gate.engine.post_github_review 등 engine 네임스페이스로 패치 가능.
Delegates to engine.py's _run_approve_decision(). Tests can patch engine namespace symbols.
"""
import logging

from src.gate.actions import GateAction, GateContext, register

logger = logging.getLogger(__name__)


class ApproveAction(GateAction):
    """Approve Gate 옵션 — auto/semi-auto 분기.
    P0-H: 실제 구현(_run_approve_decision)이 독립 SessionLocal()을 사용.
    P0-H: Actual impl (_run_approve_decision) opens its own SessionLocal().
    """

    def is_applicable(self, config) -> bool:
        """approve_mode가 'disabled'가 아닐 때 실행."""
        return config.approve_mode != "disabled"

    async def execute(self, ctx: GateContext) -> None:
        """engine.py의 _run_approve_decision에 위임한다.
        Delegates to engine.py's _run_approve_decision.
        """
        from src.gate import engine  # pylint: disable=import-outside-toplevel
        await engine._run_approve_decision(  # pylint: disable=protected-access
            config=ctx.config,
            analysis_id=ctx.analysis_id,
            github_token=ctx.github_token,
            repo_name=ctx.repo_name,
            pr_number=ctx.pr_number,
            score=ctx.score,
            result=ctx.result,
        )


register(ApproveAction())
