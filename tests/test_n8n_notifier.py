import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.n8n import notify_n8n
from src.scorer.calculator import ScoreResult


def _score():
    return ScoreResult(total=82, grade="B", code_quality_score=28, security_score=20, breakdown={})


async def test_notify_n8n_posts_to_webhook():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.notifier.n8n.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        score = ScoreResult(total=82, grade="B", code_quality_score=28, security_score=20, breakdown={})
        await notify_n8n("https://n8n.example.com/webhook/abc", "owner/repo", "abc123", 5, score)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
        assert url == "https://n8n.example.com/webhook/abc"
        payload = call_args.kwargs.get("json") or (call_args.args[1] if len(call_args.args) > 1 else {})
        assert payload["repo"] == "owner/repo"
        assert payload["score"] == 82
        assert payload["grade"] == "B"


async def test_notify_n8n_skips_when_no_url():
    with patch("src.notifier.n8n.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_cls.return_value = mock_client

        score = ScoreResult(total=80, grade="B", code_quality_score=25, security_score=20, breakdown={})
        await notify_n8n(None, "owner/repo", "abc123", None, score)
        mock_client.post.assert_not_called()


async def test_notify_n8n_raises_on_error():
    with patch("src.notifier.n8n.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("Connection error")
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        score = ScoreResult(total=80, grade="B", code_quality_score=25, security_score=20, breakdown={})
        with pytest.raises(Exception, match="Connection error"):
            await notify_n8n("https://n8n.example.com/webhook/abc", "owner/repo", "abc123", None, score)
