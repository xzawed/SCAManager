"""AutoMergeAction — score 임계값 초과 시 PR을 자동 merge하는 Gate 액션.
AutoMergeAction — auto-merges PR when score meets the merge threshold.

구현은 engine.py의 _run_auto_merge()에 위임한다.
테스트는 src.gate.engine.* engine 네임스페이스로 패치 가능.
Delegates to engine.py's _run_auto_merge(). Tests can patch engine namespace symbols.
"""
import logging

from src.gate._common import ai_review_failed
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

        정적분석 불완전(타임아웃) 시 auto-merge 차단 — 미분석 코드는 점수가 인플레이션될 수
        있으므로 자동 머지하지 않는다 (Approve/Review 옵션은 영향 없음).
        Block auto-merge when static analysis is incomplete (timeout) — unanalyzed code may have an
        inflated score, so never auto-merge it (Approve/Review options are unaffected).
        """
        if ctx.result.get("static_analysis_incomplete"):
            logger.warning(
                "static analysis incomplete — auto-merge skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        # C22: AI 리뷰 diff 절단(truncated) 시 차단 — 잘린 부분 미검토로 점수가 인플레될 수
        # 있어 자동 머지하지 않는다 (static_analysis_incomplete 대칭).
        # C22: block when the AI-review diff was truncated — the unseen part may inflate the score,
        # so never auto-merge it (mirrors static_analysis_incomplete).
        if ctx.result.get("ai_review_truncated"):
            logger.warning(
                "AI review diff truncated — auto-merge skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        # AI 리뷰 실제 실패(api_error/parse_error) 시도 차단 — 중립-고점 기본값(44점)이
        # 점수를 인플레이션해 미검증 코드가 자동 머지되는 fail-open 방지 (#8, 정적분석 대칭).
        # Also block when the AI review genuinely failed — its neutral-high defaults inflate
        # the score, which would auto-merge unvetted code (#8, symmetric with static analysis).
        if ai_review_failed(ctx.result):
            logger.warning(
                "AI review failed (%s) — auto-merge skipped (repo=%s, pr=%s)",
                ctx.result.get("ai_review_status"), ctx.repo_name, ctx.pr_number,
            )
            return
        # 2nd-LLM 검증 가드는 engine._run_auto_merge 진입부로 단일출처화됨(#859 P1-1 parity) —
        # 자동/반자동 양 경로가 공유한다. result 를 전달해 가드가 diff/리뷰 요약을 검증할 수 있게 한다.
        # The 2nd-LLM verifier guard is single-sourced into engine._run_auto_merge (#859 P1-1 parity),
        # shared by auto/semi-auto paths. Pass result so the guard can judge the diff/review summary.
        from src.gate import engine  # pylint: disable=import-outside-toplevel
        await engine._run_auto_merge(  # pylint: disable=protected-access
            ctx.config,
            ctx.github_token,
            ctx.repo_name,
            ctx.pr_number,
            ctx.score,
            analysis_id=ctx.analysis_id,
            result=ctx.result,
        )


register(AutoMergeAction())
