import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.gate.github_review import post_github_review


async def test_post_github_review_approve():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        await post_github_review("token", "owner/repo", 5, "approve", "LGTM")
        call_str = str(mock_client.post.call_args)
        assert "APPROVE" in call_str
        assert "owner/repo" in call_str

async def test_post_github_review_reject():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        await post_github_review("token", "owner/repo", 5, "reject", "Needs work")
        assert "REQUEST_CHANGES" in str(mock_client.post.call_args)

async def test_post_github_review_raises_on_error():
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("GitHub API error")
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        with pytest.raises(Exception, match="GitHub API error"):
            await post_github_review("token", "owner/repo", 5, "approve", "OK")
