"""_AutoMergeAction — 점수 기준 이상 시 squash merge 자동 실행."""
from __future__ import annotations

import logging
from html import escape

import httpx

from src.config import settings
from src.gate.github_review import merge_pr
from src.gate.registry import GateContext, register
from src.notifier.telegram import telegram_post_message

logger = logging.getLogger(__name__)


class _AutoMergeAction:
    name = "auto_merge"

    def is_enabled(self, ctx: GateContext) -> bool:
        """auto_merge=True 이고 score >= merge_threshold 이면 실행.

        approve_mode 와 무관 — 완전 독립.
        """
        score = ctx.result.get("score", 0)
        return bool(ctx.config.auto_merge) and score >= ctx.config.merge_threshold

    async def run(self, ctx: GateContext) -> None:
        """squash merge 를 시도하고 실패 시 Telegram 알림."""
        score = ctx.result.get("score", 0)
        try:
            ok, reason = await merge_pr(ctx.github_token, ctx.repo_name, ctx.pr_number)
            if ok:
                logger.info("PR #%d auto-merged: %s", ctx.pr_number, ctx.repo_name)
                return
            logger.warning(
                "PR #%d auto-merge 실패 (repo=%s): %s",
                ctx.pr_number, ctx.repo_name, reason,
            )
            await _notify_merge_failure(
                repo_name=ctx.repo_name,
                pr_number=ctx.pr_number,
                score=score,
                threshold=ctx.config.merge_threshold,
                reason=reason or "unknown",
                chat_id=ctx.config.notify_chat_id or settings.telegram_chat_id,
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Auto Merge 실패: %s", exc)


async def _notify_merge_failure(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    chat_id: str | None,
) -> None:
    """auto_merge 실패를 Telegram 으로 알린다. chat_id 없으면 스킵."""
    if not chat_id or not settings.telegram_bot_token:
        return
    text = (
        "⚠️ <b>Auto Merge 실패</b>\n"
        f"📁 <code>{escape(repo_name)}</code> — PR #{pr_number}\n"
        f"점수: {score}점 (기준 {threshold}점 이상)\n"
        f"사유: <code>{escape(reason)}</code>"
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token,
            chat_id,
            {"text": text, "parse_mode": "HTML"},
        )
    except httpx.HTTPError as exc:
        logger.warning("Telegram merge-failure 알림 실패: %s", exc)


register(_AutoMergeAction())
