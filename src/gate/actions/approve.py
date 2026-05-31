"""ApproveAction — score 기반 GitHub Approve/Reject 또는 Telegram 반자동 요청 Gate 액션.
ApproveAction — approves/rejects PRs via GitHub review or sends Telegram semi-auto request.

Sprint E-final: 구현이 이 모듈에 직접 포함됨 (engine.py 위임 제거).
Sprint E-final: Implementation lives here directly (delegation to engine.py removed).
"""
import logging

import httpx

from src.config import settings
from src.database import SessionLocal
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
        """Auto Approve — score 기준 approve/reject/skip."""
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
        """Semi-auto Approve — Telegram 인라인 키보드 발송."""
        if not ctx.config.notify_chat_id:
            logger.warning(
                "semi-auto 모드이나 notify_chat_id 미설정: %s",
                sanitize_for_log(ctx.repo_name),
            )
            return
        try:
            score_result = _score_from_result(ctx.result)
            await send_gate_request(
                bot_token=settings.telegram_bot_token,
                chat_id=ctx.config.notify_chat_id,
                analysis_id=ctx.analysis_id,
                repo_full_name=ctx.repo_name,
                pr_number=ctx.pr_number,
                score_result=score_result,
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Telegram Gate 요청 실패: %s", type(exc).__name__)


register(ApproveAction())
