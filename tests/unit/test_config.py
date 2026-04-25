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


# ---------------------------------------------------------------------------
# 온프레미스 PostgreSQL 전환을 위한 신규 설정 필드 테스트 (Task 2)
# ---------------------------------------------------------------------------

def _reload_settings(monkeypatch, extra: dict | None = None) -> "Settings":
    """공통 필수 환경변수를 설정한 뒤 src.config를 reload해 신선한 Settings 반환."""
    import importlib
    import src.config as cfg

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    if extra:
        for k, v in extra.items():
            monkeypatch.setenv(k, v)
    importlib.reload(cfg)
    return cfg.settings


def test_db_sslmode_default_empty(monkeypatch):
    # db_sslmode 필드는 기본값이 빈 문자열이어야 한다
    # db_sslmode field default must be an empty string.
    s = _reload_settings(monkeypatch)
    assert s.db_sslmode == ""


def test_db_force_ipv4_default_false(monkeypatch):
    # db_force_ipv4 필드는 기본값이 False여야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_force_ipv4 is False


def test_db_pool_size_default_5(monkeypatch):
    # db_pool_size 필드는 기본값이 5여야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_pool_size == 5


def test_db_max_overflow_default_10(monkeypatch):
    # db_max_overflow 필드는 기본값이 10이어야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_max_overflow == 10


def test_db_pool_timeout_default_30(monkeypatch):
    # db_pool_timeout 필드는 기본값이 30이어야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_pool_timeout == 30


def test_db_pool_recycle_default_1800(monkeypatch):
    # db_pool_recycle 필드는 기본값이 1800이어야 한다
    s = _reload_settings(monkeypatch)
    assert s.db_pool_recycle == 1800


def test_db_sslmode_reads_from_env(monkeypatch):
    # DB_SSLMODE 환경변수 설정 시 해당 값이 반영되어야 한다
    # When DB_SSLMODE env var is set, that value must be reflected.
    s = _reload_settings(monkeypatch, extra={"DB_SSLMODE": "require"})
    assert s.db_sslmode == "require"


def test_db_force_ipv4_reads_from_env(monkeypatch):
    # DB_FORCE_IPV4=true 환경변수 설정 시 True로 반영되어야 한다
    s = _reload_settings(monkeypatch, extra={"DB_FORCE_IPV4": "true"})
    assert s.db_force_ipv4 is True


def test_db_pool_size_reads_from_env(monkeypatch):
    # DB_POOL_SIZE 환경변수 설정 시 해당 정수값이 반영되어야 한다
    # When DB_POOL_SIZE env var is set, the integer value must be reflected.
    s = _reload_settings(monkeypatch, extra={"DB_POOL_SIZE": "20"})
    assert s.db_pool_size == 20


def test_non_supabase_url_no_ssl_added(monkeypatch):
    # 일반 온프레미스 URL에는 sslmode가 자동으로 추가되지 않아야 한다
    # A plain on-premises URL must not have sslmode added automatically.
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://u:p@localhost/db"},
    )
    assert "sslmode" not in s.database_url


def test_supabase_url_ssl_added(monkeypatch):
    # supabase.co URL에는 기존 동작대로 sslmode=require가 자동 추가되어야 한다
    s = _reload_settings(
        monkeypatch,
        extra={"DATABASE_URL": "postgresql://u:p@db.abc.supabase.co/postgres"},
    )
    assert "sslmode=require" in s.database_url
