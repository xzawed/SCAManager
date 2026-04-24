import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.railway_client.models import (
    RailwayDeployEvent,
    RailwayProjectInfo,
    RailwayCommitInfo,
)
from src.notifier.railway_issue import create_deploy_failure_issue, _build_issue_body


_EVENT = RailwayDeployEvent(
    deployment_id="deploy-abc",
    status="BUILD_FAILED",
    timestamp="2026-04-20T10:00:00Z",
    project=RailwayProjectInfo(
        project_id="proj-123",
        project_name="my-project",
        environment_name="production",
    ),
    commit=RailwayCommitInfo(
        commit_sha="deadbeef1234567890abcdef",
        commit_message="feat: add feature",
        repo_full_name="owner/repo",
    ),
)


def test_build_issue_body_contains_marker():
    """Issue 본문에 deployment_id 마커가 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail="log line 1\nlog line 2")
    assert "<!-- scamanager-railway-deployment-id:deploy-abc -->" in body


def test_build_issue_body_contains_commit():
    """Issue 본문에 커밋 SHA 축약(7자)이 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail=None)
    assert "deadbee" in body


def test_build_issue_body_no_log_fallback():
    """logs_tail=None 이면 대체 문자열이 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail=None)
    assert "로그를 가져오지 못했습니다" in body


def test_build_issue_body_with_logs():
    """logs_tail 이 있으면 본문에 포함되어야 한다."""
    body = _build_issue_body(event=_EVENT, logs_tail="ERROR: build failed")
    assert "ERROR: build failed" in body


@pytest.mark.asyncio
async def test_create_deploy_failure_issue_creates_issue():
    """중복 없을 때 Issue 번호를 반환해야 한다."""
    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json.return_value = {"total_count": 0, "items": []}

    create_resp = MagicMock()
    create_resp.raise_for_status = MagicMock()
    create_resp.json.return_value = {"number": 42}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.post = AsyncMock(return_value=create_resp)

    with patch("src.notifier.railway_issue.get_http_client", return_value=mock_client):
        result = await create_deploy_failure_issue(
            github_token="ghp_test",
            repo_full_name="owner/repo",
            event=_EVENT,
            logs_tail="build log",
        )

    assert result == 42


@pytest.mark.asyncio
async def test_create_deploy_failure_issue_dedup():
    """동일 deployment_id Issue 가 이미 존재하면 None 을 반환해야 한다."""
    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json.return_value = {
        "total_count": 1,
        "items": [{"number": 10}],
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)

    with patch("src.notifier.railway_issue.get_http_client", return_value=mock_client):
        result = await create_deploy_failure_issue(
            github_token="ghp_test",
            repo_full_name="owner/repo",
            event=_EVENT,
            logs_tail=None,
        )

    assert result is None
    mock_client.post.assert_not_called()


@pytest.mark.asyncio
async def test_create_deploy_failure_issue_github_error_returns_none():
    """GitHub Issue 생성 실패 시 None 반환 (파이프라인 무중단)."""
    import httpx as _httpx
    search_resp = MagicMock()
    search_resp.raise_for_status = MagicMock()
    search_resp.json.return_value = {"total_count": 0, "items": []}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.post = AsyncMock(side_effect=_httpx.HTTPStatusError(
        "403", request=MagicMock(), response=MagicMock()
    ))

    with patch("src.notifier.railway_issue.get_http_client", return_value=mock_client):
        result = await create_deploy_failure_issue(
            github_token="ghp_test",
            repo_full_name="owner/repo",
            event=_EVENT,
            logs_tail=None,
        )

    assert result is None
