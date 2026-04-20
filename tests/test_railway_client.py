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
