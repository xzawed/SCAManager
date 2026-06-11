"""AutoMergeAction — score 임계값 초과 시 PR을 자동 merge하는 Gate 액션.
AutoMergeAction — auto-merges PR when score meets the merge threshold.

구현은 engine.py의 _run_auto_merge()에 위임한다.
테스트는 src.gate.engine.* engine 네임스페이스로 패치 가능.
Delegates to engine.py's _run_auto_merge(). Tests can patch engine namespace symbols.
"""
import logging

from src.gate._common import ai_review_failed
from src.gate.actions import GateAction, GateContext, register
from src.gate.merge_reasons import VERIFIER_BLOCKED, VERIFIER_ERROR
from src.gate.merge_verifier import (
    VERIFIER_OK, should_verify, verify_merge_safety,
)
from src.notifier.github_comment import post_plain_pr_comment

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
        # 2nd-LLM 검증 가드 — 경계 밴드 자동머지만 OpenAI 검증자로 안전성/조작 판정.
        # 키 미설정/밴드 밖/kill-switch 면 should_verify=False → 검증 skip(현행 동작 보존).
        # 2nd-LLM verifier guard — only borderline-band auto-merges are verified.
        # When key unset / outside band / kill-switch off → should_verify=False → skip (behavior preserved).
        if should_verify(score=ctx.score, merge_threshold=ctx.config.merge_threshold):
            verdict = await verify_merge_safety(ctx)
            if verdict.status != VERIFIER_OK or not verdict.safe or verdict.manipulation_detected:
                reason = "; ".join(verdict.reasons) or verdict.status
                # 검증자 오류(api/parse) = VERIFIER_ERROR / 정상 판정의 unsafe·조작 = VERIFIER_BLOCKED.
                # 구조화 로그에 정규 태그 기록(merge_attempt DB row 는 engine 단일출처 규칙 보존 — api.md).
                # Verifier error → VERIFIER_ERROR; a successful unsafe/manipulation verdict → VERIFIER_BLOCKED.
                # Tag emitted in the structured log (merge_attempt DB row stays engine-single-source per api.md).
                block_tag = VERIFIER_ERROR if verdict.status != VERIFIER_OK else VERIFIER_BLOCKED
                logger.warning(
                    "merge verifier blocked auto-merge (tag=%s status=%s) — repo=%s pr=%s: %s",
                    block_tag, verdict.status, ctx.repo_name, ctx.pr_number, reason,
                )
                try:
                    await post_plain_pr_comment(
                        ctx.github_token, ctx.repo_name, ctx.pr_number,
                        f"🛑 Auto-merge withheld by the 2nd-LLM cross-vendor verifier "
                        f"(Claude review ↔ GPT verification) — merge-safety check failed.\n\n"
                        f"- status: `{verdict.status}`\n- reasons: {reason}",
                    )
                except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
                    logger.exception("verifier block comment failed (repo=%s pr=%s)",
                                     ctx.repo_name, ctx.pr_number)
                return
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
