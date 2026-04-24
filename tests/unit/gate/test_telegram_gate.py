import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, patch, MagicMock
from src.gate.telegram_gate import send_gate_request
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
