"""Telegram semi-auto gate — sends inline keyboard review request to chat."""
import hashlib
import hmac

from src.notifier.telegram import telegram_post_message
from src.scorer.calculator import ScoreResult


def _gate_callback_token(bot_token: str, analysis_id: int) -> str:
    """콜백 데이터 위변조 방지용 HMAC 토큰 (SHA-256 전체 hex, 256-bit).
    Full SHA-256 hex HMAC token for callback integrity verification (256-bit)."""
    return hmac.new(
        bot_token.encode(), str(analysis_id).encode(), digestmod=hashlib.sha256
    ).hexdigest()  # 전체 64자 사용 — 앞 32자만 쓰는 128-bit 절단에서 256-bit 로 강화


async def send_gate_request(
    *,
    bot_token: str,
    chat_id: str,
    analysis_id: int,
    repo_full_name: str,
    pr_number: int,
    score_result: ScoreResult,
) -> None:
    """반자동 Gate PR 검토 요청을 Telegram 인라인 키보드로 전송한다."""
    text = (
        f"🔍 *PR 검토 요청*\n"
        f"리포: `{repo_full_name}` — PR #{pr_number}\n"
        f"점수: *{score_result.total}점* ({score_result.grade}등급)\n\n"
        f"승인 또는 반려를 선택하세요."
    )
    token = _gate_callback_token(bot_token, analysis_id)
    reply_markup = {
        "inline_keyboard": [[
            {"text": "✅ 승인", "callback_data": f"gate:approve:{analysis_id}:{token}"},
            {"text": "❌ 반려", "callback_data": f"gate:reject:{analysis_id}:{token}"},
        ]]
    }
    await telegram_post_message(bot_token, chat_id, {
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup,
    })
