"""Telegram semi-auto gate — sends inline keyboard review request to chat."""
import hashlib
import hmac

from src.notifier.telegram import telegram_post_message
from src.scorer.calculator import ScoreResult


def _gate_callback_token(bot_token: str, analysis_id: int) -> str:
    """콜백 데이터 위변조 방지용 HMAC-SHA256 토큰 — 32자 hex (128-bit 절단).
    HMAC-SHA256 callback integrity token truncated to 32 hex chars (128-bit).

    Telegram callback_data 한도 64바이트 준수:
    "gate:approve:<id>:<32-char-token>" 최대 ~51바이트 (id≤99999 기준).
    Telegram callback_data 64-byte limit compliance:
    "gate:approve:<id>:<32-char-token>" is at most ~51 bytes (id≤99999).
    128-bit HMAC 절단은 NIST SP 800-107 기준 충분한 보안 강도 제공.
    128-bit HMAC truncation provides sufficient security per NIST SP 800-107."""
    return hmac.new(
        bot_token.encode(), str(analysis_id).encode(), digestmod=hashlib.sha256
    ).hexdigest()[:32]  # 32자(128-bit) — Telegram 64-byte 한도 준수 필수


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
