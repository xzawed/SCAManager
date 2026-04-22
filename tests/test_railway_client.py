import dataclasses
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from src.config_manager.manager import RepoConfigData  # noqa: E402
from src.models.repo_config import RepoConfig  # noqa: E402


def test_repo_config_has_railway_fields():
    """RepoConfig ORM 에 Railway 필드 3개가 존재해야 한다."""
    assert hasattr(RepoConfig, "railway_deploy_alerts")
    assert hasattr(RepoConfig, "railway_webhook_token")
    assert hasattr(RepoConfig, "railway_api_token")


def test_repo_config_railway_alerts_default():
    """RepoConfig 기본값 — railway_deploy_alerts=False."""
    config = RepoConfig(repo_full_name="owner/repo")
    assert config.railway_deploy_alerts is False


def test_repo_config_data_has_railway_alerts():
    """RepoConfigData 에 railway_deploy_alerts 필드 기본값 False."""
    data = RepoConfigData(repo_full_name="owner/repo")
    assert data.railway_deploy_alerts is False


def test_repo_config_data_railway_alerts_settable():
    """RepoConfigData 에 railway_deploy_alerts=True 설정 가능."""
    data = RepoConfigData(repo_full_name="owner/repo", railway_deploy_alerts=True)
    assert data.railway_deploy_alerts is True


def test_repo_config_webhook_token_not_in_config_data():
    """railway_webhook_token 은 RepoConfigData 에 포함되지 않아야 한다 (ORM 직접 관리)."""
    field_names = {f.name for f in dataclasses.fields(RepoConfigData)}
    assert "railway_webhook_token" not in field_names
    assert "railway_api_token" not in field_names


from src.railway_client.webhook import parse_railway_payload  # noqa: E402


_VALID_PAYLOAD = {
    "type": "DEPLOY",
    "status": "BUILD_FAILED",
    "timestamp": "2026-04-20T10:00:00Z",
    "deployment": {
        "id": "deploy-abc123",
        "meta": {
            "commitSha": "deadbeef1234567890abcdef",
            "commitMessage": "feat: add feature",
            "repo": "owner/repo",
        },
    },
    "project": {"id": "proj-123", "name": "my-project"},
    "environment": {"name": "production"},
}


def test_parse_valid_build_failed():
    """BUILD_FAILED 이벤트는 nested RailwayDeployEvent 를 반환해야 한다."""
    event = parse_railway_payload(_VALID_PAYLOAD)
    assert event is not None
    assert event.deployment_id == "deploy-abc123"
    assert event.status == "BUILD_FAILED"
    assert event.project.project_id == "proj-123"
    assert event.project.project_name == "my-project"
    assert event.project.environment_name == "production"
    assert event.commit.commit_sha == "deadbeef1234567890abcdef"
    assert event.commit.repo_full_name == "owner/repo"


def test_parse_failed_status():
    """FAILED 상태도 유효 이벤트로 파싱되어야 한다."""
    payload = dict(_VALID_PAYLOAD, status="FAILED")
    event = parse_railway_payload(payload)
    assert event is not None
    assert event.status == "FAILED"


def test_parse_success_returns_none():
    """SUCCESS 상태는 None 을 반환해야 한다."""
    payload = dict(_VALID_PAYLOAD, status="SUCCESS")
    assert parse_railway_payload(payload) is None


def test_parse_non_deploy_type_returns_none():
    """type != DEPLOY 이면 None 을 반환해야 한다."""
    payload = dict(_VALID_PAYLOAD, type="BUILD")
    assert parse_railway_payload(payload) is None


def test_parse_missing_deployment_id_returns_none():
    """deployment.id 누락 시 None 을 반환해야 한다."""
    payload = dict(_VALID_PAYLOAD)
    payload["deployment"] = {}
    assert parse_railway_payload(payload) is None


def test_parse_missing_optional_fields():
    """project/commit 정보 없어도 파싱은 성공해야 한다."""
    payload = {
        "type": "DEPLOY",
        "status": "FAILED",
        "timestamp": "2026-04-20T10:00:00Z",
        "deployment": {"id": "deploy-xyz"},
    }
    event = parse_railway_payload(payload)
    assert event is not None
    assert event.project.project_name == ""
    assert event.commit.commit_sha is None


import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.railway_client.logs import fetch_deployment_logs, RailwayLogFetchError


@pytest.mark.asyncio
async def test_fetch_deployment_logs_success():
    """정상 응답 시 로그 줄을 합쳐서 반환해야 한다."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "data": {
            "deploymentLogs": [
                {"message": "Installing dependencies", "severity": "INFO"},
                {"message": "Build failed: exit code 1", "severity": "ERROR"},
            ]
        }
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("src.railway_client.logs.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await fetch_deployment_logs("tok", "deploy-123")

    assert "Installing dependencies" in result
    assert "Build failed" in result


@pytest.mark.asyncio
async def test_fetch_deployment_logs_http_error():
    """HTTP 오류 시 RailwayLogFetchError 를 raise 해야 한다."""
    import httpx as _httpx
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=_httpx.RequestError("timeout"))

    with patch("src.railway_client.logs.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(RailwayLogFetchError):
            await fetch_deployment_logs("tok", "deploy-123")


@pytest.mark.asyncio
async def test_fetch_deployment_logs_graphql_error():
    """GraphQL errors 필드 존재 시 RailwayLogFetchError 를 raise 해야 한다."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"errors": [{"message": "Unauthorized"}]}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_resp)

    with patch("src.railway_client.logs.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(RailwayLogFetchError):
            await fetch_deployment_logs("tok", "deploy-123")
