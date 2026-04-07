import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_list_user_repos_returns_repo_list():
    """list_user_repos는 GitHub API로 리포 목록을 반환한다."""
    from src.github_client.repos import list_user_repos

    mock_response_data = [
        {"full_name": "owner/repo-a", "private": False, "description": "Repo A"},
        {"full_name": "owner/repo-b", "private": True, "description": "Repo B"},
    ]

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response_data
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await list_user_repos("gho_test_token")

    assert len(result) == 2
    assert result[0]["full_name"] == "owner/repo-a"
    assert result[0]["private"] is False
    assert result[1]["full_name"] == "owner/repo-b"
    assert result[1]["private"] is True


@pytest.mark.asyncio
async def test_create_webhook_returns_webhook_id():
    """create_webhook은 GitHub API를 호출하고 webhook_id를 반환한다."""
    from src.github_client.repos import create_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 12345678}
    mock_resp.raise_for_status = MagicMock()

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await create_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_url="https://example.com/webhooks/github",
            secret="random_secret_hex",
        )

    assert result == 12345678
    call_kwargs = mock_client.post.call_args
    posted_json = call_kwargs.kwargs["json"]
    assert posted_json["name"] == "web"
    assert posted_json["active"] is True
    assert "push" in posted_json["events"]
    assert "pull_request" in posted_json["events"]
    assert posted_json["config"]["url"] == "https://example.com/webhooks/github"
    assert posted_json["config"]["secret"] == "random_secret_hex"


@pytest.mark.asyncio
async def test_delete_webhook_returns_true_on_204():
    """delete_webhook은 204 응답 시 True를 반환한다."""
    from src.github_client.repos import delete_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 204

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await delete_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_id=12345678,
        )

    assert result is True


@pytest.mark.asyncio
async def test_delete_webhook_returns_false_on_error():
    """delete_webhook은 204 이외 응답 시 False를 반환한다."""
    from src.github_client.repos import delete_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client_cls.return_value = mock_client

        result = await delete_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_id=12345678,
        )

    assert result is False
