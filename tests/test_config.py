import os
import pytest


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test_secret")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")

    # 기존 캐시된 settings 인스턴스 우회
    import importlib
    import src.config as cfg
    importlib.reload(cfg)

    assert cfg.settings.github_webhook_secret == "test_secret"
    assert cfg.settings.telegram_chat_id == "-100123"
