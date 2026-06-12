"""ApproveAction — score 기반 GitHub Approve/Reject 또는 Telegram 반자동 요청 Gate 액션.
ApproveAction — approves/rejects PRs via GitHub review or sends Telegram semi-auto request.

Sprint E-final: 구현이 이 모듈에 직접 포함됨 (engine.py 위임 제거).
Sprint E-final: Implementation lives here directly (delegation to engine.py removed).
"""
import logging

import httpx

from src.config import settings
from src.database import WorkerSessionLocal as SessionLocal
from src.gate._common import ai_review_failed
from src.gate._common import score_from_result as _score_from_result
from src.gate.actions import GateAction, GateContext, register
from src.gate.github_review import post_github_review
from src.gate.telegram_gate import send_gate_request
from src.i18n.loader import get_text
from src.notifier._language import resolve_notification_language
from src.repositories import gate_decision_repo
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)


class ApproveAction(GateAction):
    """Approve Gate 옵션 — auto/semi-auto 분기.
    Auto mode: approves/rejects via GitHub review based on score thresholds.
    Semi-auto mode: sends Telegram inline keyboard for human decision.

    P0-H: 독립 SessionLocal() 사용 — asyncio.gather 병렬 실행 시 Session 공유 금지.
    P0-H: Uses independent SessionLocal() — do not share with gather siblings.
    """

    def is_applicable(self, config) -> bool:
        """approve_mode가 'disabled'가 아닐 때 실행."""
        return config.approve_mode != "disabled"

    async def execute(self, ctx: GateContext) -> None:
        """설정 모드에 따라 auto/semi-auto 분기를 실행한다."""
        if ctx.config.approve_mode == "auto":
            await self._run_auto(ctx)
        elif ctx.config.approve_mode == "semi-auto":
            await self._run_semi_auto(ctx)

    async def _run_auto(self, ctx: GateContext) -> None:
        """Auto Approve — score 기준 approve/reject/skip.

        정적분석 불완전(타임아웃) 시 자동 approve 보류 — 미분석 코드는 점수가 인플레이션될 수
        있고, auto-approve 가 branch-protection "approval 시 자동머지" 를 간접 트리거할 수
        있으므로 결정을 내리지 않는다 (#779 auto-merge 가드의 approve 경로 확장).
        Hold auto-approve when static analysis is incomplete (timeout) — unanalyzed code may have an
        inflated score, and an auto-approve could indirectly trigger branch-protection
        "auto-merge on approval", so make no decision (#779 auto-merge guard extended to approve).
        """
        if ctx.result.get("static_analysis_incomplete"):
            logger.warning(
                "static analysis incomplete — auto-approve skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        # AI 리뷰 실제 실패(api_error/parse_error) 시도 보류 — 중립-고점 기본값이 점수를
        # 인플레이션하고, auto-approve 가 branch-protection "approval 시 자동머지" 를 간접
        # 트리거할 수 있으므로 결정을 내리지 않는다 (#8, auto-merge 가드의 approve 경로 확장).
        # Also hold auto-approve when the AI review genuinely failed — inflated defaults could
        # indirectly trigger branch-protection "auto-merge on approval" (#8, extends the merge guard).
        if ai_review_failed(ctx.result):
            logger.warning(
                "AI review failed (%s) — auto-approve skipped (repo=%s, pr=%s)",
                ctx.result.get("ai_review_status"), ctx.repo_name, ctx.pr_number,
            )
            return
        # 알림 언어 결정 (3-layer fallback) — GitHub PR 댓글을 리포 소유자 언어로 게시
        # Resolve notification language (3-layer fallback) — post PR review in owner's language
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
        if ctx.score >= ctx.config.approve_threshold:
            decision = "approve"
            body = get_text(
                "notifier.gate.auto_approve", language,
                score=ctx.score, threshold=ctx.config.approve_threshold,
            )
        elif ctx.score < ctx.config.reject_threshold:
            decision = "reject"
            body = get_text(
                "notifier.gate.auto_reject", language,
                score=ctx.score, threshold=ctx.config.reject_threshold,
            )
        else:
            with SessionLocal() as db:
                gate_decision_repo.upsert(db, ctx.analysis_id, "skip", "auto")
            return
        try:
            await post_github_review(
                ctx.github_token, ctx.repo_name, ctx.pr_number, decision, body,
            )
            with SessionLocal() as db:
                gate_decision_repo.upsert(db, ctx.analysis_id, decision, "auto")
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("GitHub Review 실패: %s", type(exc).__name__)

    async def _run_semi_auto(self, ctx: GateContext) -> None:
        """Semi-auto Approve — Telegram 인라인 키보드 발송.

        🔴 정적분석 불완전·AI 리뷰 실패 시 가드(_run_auto 와 대칭): 인플레 기본 점수를 사람에게
        승인 버튼으로 노출하면 오해된 점수로 approve+merge 될 수 있으므로 발송하지 않는다
        (#8/#779 fail-open 봉인의 semi-auto 경로 — 이전엔 자동 경로에만 가드 존재).
        Hold the semi-auto approval request when static analysis is incomplete or the AI review
        genuinely failed (mirrors _run_auto): showing an inflated default score on a human approval
        button could lead to approve+merge of unvetted code (#8/#779 fail-open seal for the semi-auto
        path — previously only the auto path had the guard).
        """
        if ctx.result.get("static_analysis_incomplete"):
            logger.warning(
                "static analysis incomplete — semi-auto approve skipped (repo=%s, pr=%s)",
                ctx.repo_name, ctx.pr_number,
            )
            return
        if ai_review_failed(ctx.result):
            logger.warning(
                "AI review failed (%s) — semi-auto approve skipped (repo=%s, pr=%s)",
                ctx.result.get("ai_review_status"), ctx.repo_name, ctx.pr_number,
            )
            return
        if not ctx.config.notify_chat_id:
            logger.warning(
                "semi-auto 모드이나 notify_chat_id 미설정: %s",
                sanitize_for_log(ctx.repo_name),
            )
            return
        # 알림 언어 결정 (3-layer fallback) — Telegram 검토 요청을 수신자 언어로 발송
        # Resolve notification language (3-layer fallback) — send Telegram request in recipient's language
        with SessionLocal() as db:
            language = resolve_notification_language(db, config=ctx.config)
        try:
            score_result = _score_from_result(ctx.result)
            await send_gate_request(
                bot_token=settings.telegram_bot_token,
                chat_id=ctx.config.notify_chat_id,
                analysis_id=ctx.analysis_id,
                repo_full_name=ctx.repo_name,
                pr_number=ctx.pr_number,
                score_result=score_result,
                language=language,
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Telegram Gate 요청 실패: %s", type(exc).__name__)


register(ApproveAction())
