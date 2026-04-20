import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from src.models.repo_config import RepoConfig


def test_repo_config_has_railway_fields():
    """RepoConfig ORM 에 Railway 필드 3개가 존재해야 한다."""
    assert hasattr(RepoConfig, "railway_deploy_alerts")
    assert hasattr(RepoConfig, "railway_webhook_token")
    assert hasattr(RepoConfig, "railway_api_token")


def test_repo_config_railway_alerts_default():
    """RepoConfig 기본값 — railway_deploy_alerts=False."""
    config = RepoConfig(repo_full_name="owner/repo")
    assert config.railway_deploy_alerts is False
