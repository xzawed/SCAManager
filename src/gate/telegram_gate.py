"""Telegram semi-auto gate — sends inline keyboard review request to chat."""
import hashlib
import hmac

from src.notifier.telegram import telegram_post_message
from src.scorer.calculator import ScoreResult


def _make_callback_token(bot_token: str, scope: str, payload_id: int) -> str:
    """scope + payload_id 기반 HMAC 토큰을 생성한다.
    Generate an HMAC token for the given scope and payload_id.

    scope ∈ {"gate", "cmd"} — 도메인별로 다른 HMAC을 생성하여 교차 재생 공격을 방지한다.
    scope ∈ {"gate", "cmd"} — Different HMACs per domain prevent cross-replay attacks.

    Telegram callback_data 한도 64바이트 준수:
    "gate:approve:<id>:<32-char-token>" 최대 ~51바이트 (id≤99999 기준).
    Telegram callback_data 64-byte limit compliance:
    "gate:approve:<id>:<32-char-token>" is at most ~51 bytes (id≤99999).
    128-bit HMAC 절단은 NIST SP 800-107 기준 충분한 보안 강도 제공.
    128-bit HMAC truncation provides sufficient security per NIST SP 800-107.
    """
    # scope:payload_id 를 HMAC 메시지로 사용해 도메인 격리 보장
    # Use scope:payload_id as HMAC message to guarantee domain isolation
    msg = f"{scope}:{payload_id}"
    return hmac.new(
        bot_token.encode(), msg.encode(), digestmod=hashlib.sha256
    ).hexdigest()[:32]  # 32자(128-bit) — Telegram 64-byte 한도 준수 필수
    # 32 chars (128-bit) — required to stay within Telegram's 64-byte limit


def _gate_callback_token(bot_token: str, analysis_id: int) -> str:
    """gate 도메인 콜백 토큰 생성 — _make_callback_token 의 thin wrapper.
    Generate a gate-domain callback token — thin wrapper over _make_callback_token.

    기존 호출자(webhook/providers/telegram.py 등)와의 하위 호환성 유지.
    Maintains backwards compatibility with existing callers (webhook/providers/telegram.py etc.).
    """
    # 시그니처 변경 없이 _make_callback_token 에 위임 — 기존 mock 패치 영향 없음
    # Delegates to _make_callback_token without signature change — existing mocks unaffected
    return _make_callback_token(bot_token, "gate", analysis_id)


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
