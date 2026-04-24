import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
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

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_resp)

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

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        webhook_secret = "random_secret_hex"  # NOSONAR python:S6418 — test fixture, not a real secret
        result = await create_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_url="https://example.com/webhooks/github",
            secret=webhook_secret,
        )

    assert result == 12345678
    call_kwargs = mock_client.post.call_args
    posted_json = call_kwargs.kwargs["json"]
    assert posted_json["name"] == "web"
    assert posted_json["active"] is True
    assert "push" in posted_json["events"]
    assert "pull_request" in posted_json["events"]
    assert posted_json["config"]["url"] == "https://example.com/webhooks/github"
    assert posted_json["config"]["secret"] == webhook_secret


@pytest.mark.asyncio
async def test_delete_webhook_returns_true_on_204():
    """delete_webhook은 204 응답 시 True를 반환한다."""
    from src.github_client.repos import delete_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 204

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.delete = AsyncMock(return_value=mock_resp)

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

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.delete = AsyncMock(return_value=mock_resp)

        result = await delete_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_id=12345678,
        )

    assert result is False


# ------------------------------------------------------------------
# commit_scamanager_files 테스트
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_scamanager_files_creates_new():
    # 파일이 없을 때(GET → 404) config.json과 install-hook.sh 각각 PUT 2회 호출됨
    from src.github_client.repos import commit_scamanager_files

    # GET 파일 존재 여부 조회 → 404 (파일 없음)
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 404
    mock_get_resp.json.return_value = {}

    # PUT 성공 응답
    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 201
    mock_put_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(return_value=mock_put_resp)

        await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    # 파일 2개(config.json, install-hook.sh) 각각 PUT 호출
    assert mock_client.put.call_count == 2
    put_urls = [call.args[0] for call in mock_client.put.call_args_list]
    assert any("config.json" in url for url in put_urls)
    assert any("install-hook.sh" in url for url in put_urls)


@pytest.mark.asyncio
async def test_commit_scamanager_files_updates_existing():
    # 파일이 이미 존재할 때(GET → 200 + sha) PUT 요청에 sha가 포함됨
    from src.github_client.repos import commit_scamanager_files

    existing_sha = "existingsha1234567890"

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"sha": existing_sha}

    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 200
    mock_put_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(return_value=mock_put_resp)

        await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    # PUT 요청 body에 sha가 포함되어야 함
    assert mock_client.put.call_count == 2
    for call in mock_client.put.call_args_list:
        put_body = call.kwargs.get("json", {})
        assert put_body.get("sha") == existing_sha


@pytest.mark.asyncio
async def test_commit_scamanager_files_returns_true_on_success():
    # 모든 PUT 성공 시 True 반환
    from src.github_client.repos import commit_scamanager_files

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 404
    mock_get_resp.json.return_value = {}

    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 201
    mock_put_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(return_value=mock_put_resp)

        result = await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    assert result is True


@pytest.mark.asyncio
async def test_commit_scamanager_files_returns_false_on_error():
    # PUT 요청 중 예외 발생(httpx.HTTPStatusError 등) 시 False 반환
    from src.github_client.repos import commit_scamanager_files

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 404
    mock_get_resp.json.return_value = {}

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "API Error",
                request=MagicMock(),
                response=MagicMock(status_code=422),
            )
        )

        result = await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    assert result is False
