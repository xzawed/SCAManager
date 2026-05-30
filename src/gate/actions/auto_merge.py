"""AutoMergeAction — score 임계값 초과 시 PR을 자동 merge하는 Gate 액션.
AutoMergeAction — auto-merges PR when score meets the merge threshold.

구현은 engine.py의 _run_auto_merge()에 위임한다.
테스트는 src.gate.engine.* engine 네임스페이스로 패치 가능.
Delegates to engine.py's _run_auto_merge(). Tests can patch engine namespace symbols.
"""
import logging

from src.gate.actions import GateAction, GateContext, register

logger = logging.getLogger(__name__)


# engine.py에서 사용되던 _run_auto_merge_action_impl은 더 이상 필요 없음.
# _run_auto_merge_action_impl is no longer needed — AutoMergeAction delegates directly.
async def _run_auto_merge_action_impl(*args, **kwargs):  # pylint: disable=unused-argument
    """하위 호환 stub — test_gate_actions.py의 mock 타겟 유지용.
    Backward-compat stub — kept as mock target for test_gate_actions.py.
    실제 로직은 engine._run_auto_merge 에 위임됨.
    Actual logic is delegated to engine._run_auto_merge.
    """
    from src.gate import engine  # pylint: disable=import-outside-toplevel
    await engine._run_auto_merge(*args, **kwargs)  # pylint: disable=protected-access


class AutoMergeAction(GateAction):
    """Auto Merge Gate 옵션 — score >= merge_threshold 시 squash merge.
    P0-H: 실제 구현(_run_auto_merge)이 독립 SessionLocal()을 사용.
    P0-H: Actual impl (_run_auto_merge) opens its own SessionLocal().
    """

    def is_applicable(self, config) -> bool:
        """auto_merge=True일 때 실행 (score 체크는 execute()에서)."""
        return bool(config.auto_merge)

    async def execute(self, ctx: GateContext) -> None:
        """engine.py의 _run_auto_merge에 위임한다.
        Delegates to engine.py's _run_auto_merge.
        """
        from src.gate import engine  # pylint: disable=import-outside-toplevel
        await engine._run_auto_merge(  # pylint: disable=protected-access
            ctx.config,
            ctx.github_token,
            ctx.repo_name,
            ctx.pr_number,
            ctx.score,
            analysis_id=ctx.analysis_id,
        )


register(AutoMergeAction())
