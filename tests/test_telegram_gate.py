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
    with patch("src.gate.telegram_gate.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        await send_gate_request("123:ABC", "-100999", 42, "owner/repo", 7, score_result)
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert payload["chat_id"] == "-100999"
        assert "inline_keyboard" in str(payload.get("reply_markup", ""))


async def test_send_gate_request_includes_analysis_id_in_callback():
    score_result = ScoreResult(total=60, grade="C", code_quality_score=20, security_score=15, breakdown={})
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.telegram_gate.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        await send_gate_request("123:ABC", "-100999", 99, "owner/repo", 3, score_result)
        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args.args[1]
        assert "99" in str(payload.get("reply_markup", ""))
