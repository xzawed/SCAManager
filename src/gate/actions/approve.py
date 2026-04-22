"""_ApproveAction — approve_mode 에 따른 GitHub APPROVE/REQUEST_CHANGES 또는 Telegram 요청."""
from __future__ import annotations

import logging

import httpx

from src.config import settings
from src.gate._common import score_from_result
from src.gate.github_review import post_github_review
from src.gate.registry import GateContext, register
from src.gate.telegram_gate import send_gate_request
from src.repositories import gate_decision_repo

logger = logging.getLogger(__name__)


class _ApproveAction:  # pylint: disable=too-few-public-methods
    name = "approve"

    def is_enabled(self, ctx: GateContext) -> bool:
        """approve_mode 가 auto 또는 semi-auto 이면 실행."""
        return ctx.config.approve_mode in ("auto", "semi-auto")

    async def run(self, ctx: GateContext) -> None:  # noqa: C901
        """approve_mode (auto | semi-auto) 에 따라 승인/반려/Telegram 요청."""
        config = ctx.config
        score = ctx.result.get("score", 0)

        if config.approve_mode == "auto":
            await self._run_auto(ctx, score)
        elif config.approve_mode == "semi-auto":
            await self._run_semi_auto(ctx)

    async def _run_auto(self, ctx: GateContext, score: int) -> None:
        config = ctx.config
        if score >= config.approve_threshold:
            decision = "approve"
            body = f"✅ 자동 승인: 점수 {score}점 (기준: {config.approve_threshold}점 이상)"
        elif score < config.reject_threshold:
            decision = "reject"
            body = f"❌ 자동 반려: 점수 {score}점 (기준: {config.reject_threshold}점 미만)"
        else:
            gate_decision_repo.upsert(ctx.db, ctx.analysis_id, "skip", "auto")
            return

        try:
            await post_github_review(
                ctx.github_token, ctx.repo_name, ctx.pr_number, decision, body
            )
            gate_decision_repo.upsert(ctx.db, ctx.analysis_id, decision, "auto")
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("GitHub Review 실패: %s", exc)

    async def _run_semi_auto(self, ctx: GateContext) -> None:
        config = ctx.config
        if not config.notify_chat_id:
            logger.warning("semi-auto 모드이나 notify_chat_id 미설정: %s", ctx.repo_name)
            return
        try:
            score_result = score_from_result(ctx.result)
            await send_gate_request(
                bot_token=settings.telegram_bot_token,
                chat_id=config.notify_chat_id,
                analysis_id=ctx.analysis_id,
                repo_full_name=ctx.repo_name,
                pr_number=ctx.pr_number,
                score_result=score_result,
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Telegram Gate 요청 실패: %s", exc)


register(_ApproveAction())
