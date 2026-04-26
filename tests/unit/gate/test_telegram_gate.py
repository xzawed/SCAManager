import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, patch, MagicMock
from src.gate.telegram_gate import (
    send_gate_request,
    _gate_callback_token,
    _make_callback_token,
)
from src.scorer.calculator import ScoreResult


async def test_send_gate_request_calls_telegram_api():
    score_result = ScoreResult(total=72, grade="B", code_quality_score=25, security_score=17, breakdown={})
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    # telegram_gate는 notifier.telegram.telegram_post_message를 사용
    with patch("src.notifier.telegram.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        await send_gate_request(
            bot_token="123:ABC",
            chat_id="-100999",
            analysis_id=42,
            repo_full_name="owner/repo",
            pr_number=7,
            score_result=score_result,
        )
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert payload["chat_id"] == "-100999"
        assert "inline_keyboard" in str(payload.get("reply_markup", ""))


async def test_send_gate_request_includes_analysis_id_in_callback():
    score_result = ScoreResult(total=60, grade="C", code_quality_score=20, security_score=15, breakdown={})
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.notifier.telegram.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        await send_gate_request(
            bot_token="123:ABC",
            chat_id="-100999",
            analysis_id=99,
            repo_full_name="owner/repo",
            pr_number=3,
            score_result=score_result,
        )
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert "99" in str(payload.get("reply_markup", ""))


def test_make_callback_token_scope_isolation():
    """다른 scope는 다른 HMAC을 생성한다 (도메인 격리).
    Different scopes produce different HMACs (domain isolation).
    """
    # "gate" 와 "cmd" scope 가 동일 payload_id 에서 서로 다른 토큰을 만들어야 함
    # "gate" and "cmd" scopes must produce different tokens for the same payload_id
    token_gate = _make_callback_token("bot_secret", "gate", 123)
    token_cmd = _make_callback_token("bot_secret", "cmd", 123)
    assert token_gate != token_cmd


def test_legacy_gate_wrapper_backwards_compatible():
    """_gate_callback_token 은 _make_callback_token("gate", id) 와 동일한 결과를 반환한다.
    _gate_callback_token returns the same result as _make_callback_token("gate", id).
    """
    # 기존 호출 코드(webhook/providers/telegram.py 등)가 영향받지 않아야 함
    # Existing callers (webhook/providers/telegram.py etc.) must not be affected
    bot_token = "test_bot_token"
    analysis_id = 456
    assert _gate_callback_token(bot_token, analysis_id) == _make_callback_token(
        bot_token, "gate", analysis_id
    )


def test_callback_data_within_64_bytes_all_commands():
    """모든 cmd: callback_data 가 Telegram 64-byte 한계 내에 있다.
    All cmd: callback_data strings stay within Telegram's 64-byte limit.
    """
    # Telegram callback_data 최대 64 바이트 — 이를 초과하면 sendMessage API 가 오류를 반환함
    # Telegram callback_data max is 64 bytes — exceeding it causes sendMessage API error
    bot_token = "any_token"
    repo_id = 9999  # 최대 4자리 숫자 가정 / assume max 4-digit repo id
    token = _make_callback_token(bot_token, "cmd", repo_id)
    candidates = [
        f"cmd:set:{repo_id}:{token}",
        f"cmd:stats:{repo_id}:{token}",
        f"cmd:settings:{repo_id}:{token}",
        f"cmd:connect:{token}",
    ]
    for data in candidates:
        assert len(data.encode()) <= 64, (
            f"callback_data too long: {data!r} ({len(data.encode())} bytes)"
        )
