"""tests/test_database.py

src/database.py의 _build_connect_args() 함수와 engine pool 설정을 검증한다.
_build_connect_args는 Task 2 구현 전까지 존재하지 않으므로 현재 테스트는 실패(Red)해야 한다.
"""
import os
import importlib
from unittest.mock import patch, MagicMock

import pytest

# conftest.py가 먼저 환경변수를 주입하므로 src import 전 추가 설정 불필요.
# 단, 각 테스트에서 settings를 재구성할 때 monkeypatch로 제어한다.


def _reload_with_settings(monkeypatch, *, db_sslmode: str = "", db_force_ipv4: bool = False,
                           db_pool_size: int = 5, db_max_overflow: int = 10,
                           db_pool_timeout: int = 30, db_pool_recycle: int = 1800):
    """지정한 DB 관련 환경변수로 src.config와 src.database를 reload한 뒤
    (settings, database_module) 튜플을 반환한다."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    monkeypatch.setenv("DB_SSLMODE", db_sslmode)
    monkeypatch.setenv("DB_FORCE_IPV4", "true" if db_force_ipv4 else "false")
    monkeypatch.setenv("DB_POOL_SIZE", str(db_pool_size))
    monkeypatch.setenv("DB_MAX_OVERFLOW", str(db_max_overflow))
    monkeypatch.setenv("DB_POOL_TIMEOUT", str(db_pool_timeout))
    monkeypatch.setenv("DB_POOL_RECYCLE", str(db_pool_recycle))

    import src.config as cfg
    importlib.reload(cfg)
    import src.database as db_mod
    importlib.reload(db_mod)
    return cfg.settings, db_mod


# ---------------------------------------------------------------------------
# _build_connect_args 단위 테스트
# ---------------------------------------------------------------------------

class TestBuildConnectArgs:
    """_build_connect_args(url) 함수의 반환값을 검증한다."""

    def test_build_connect_args_defaults_empty_dict(self, monkeypatch):
        # db_force_ipv4=False, db_sslmode="" 기본값이면 빈 dict를 반환해야 한다
        _, db_mod = _reload_with_settings(monkeypatch)
        result = db_mod._build_connect_args("sqlite:///:memory:")
        assert result == {}

    def test_build_connect_args_with_sslmode(self, monkeypatch):
        # db_sslmode="require" 설정 시 반환 dict에 sslmode 키가 포함되어야 한다
        _, db_mod = _reload_with_settings(monkeypatch, db_sslmode="require")
        result = db_mod._build_connect_args("postgresql://u:p@localhost/db")
        assert result.get("sslmode") == "require"

    def test_build_connect_args_sslmode_disable(self, monkeypatch):
        # db_sslmode="disable" 설정 시 sslmode=disable이 반영되어야 한다
        _, db_mod = _reload_with_settings(monkeypatch, db_sslmode="disable")
        result = db_mod._build_connect_args("postgresql://u:p@localhost/db")
        assert result.get("sslmode") == "disable"

    def test_build_connect_args_sslmode_empty_not_in_result(self, monkeypatch):
        # db_sslmode="" 기본값이면 반환 dict에 sslmode 키가 없어야 한다
        _, db_mod = _reload_with_settings(monkeypatch, db_sslmode="")
        result = db_mod._build_connect_args("postgresql://u:p@localhost/db")
        assert "sslmode" not in result

    def test_build_connect_args_ipv4_disabled(self, monkeypatch):
        # db_force_ipv4=False 이면 hostaddr 키가 반환 dict에 없어야 한다
        _, db_mod = _reload_with_settings(monkeypatch, db_force_ipv4=False)
        result = db_mod._build_connect_args("postgresql://u:p@localhost/db")
        assert "hostaddr" not in result

    def test_build_connect_args_ipv4_enabled_calls_ipv4_helper(self, monkeypatch):
        # db_force_ipv4=True 이면 _ipv4_connect_args()가 호출되어 결과가 merge되어야 한다
        _, db_mod = _reload_with_settings(monkeypatch, db_force_ipv4=True)
        fake_ipv4 = {"hostaddr": "1.2.3.4"}
        with patch.object(db_mod, "_ipv4_connect_args", return_value=fake_ipv4) as mock_ipv4:
            result = db_mod._build_connect_args("postgresql://u:p@some-host/db")
        mock_ipv4.assert_called_once()
        assert result.get("hostaddr") == "1.2.3.4"

    def test_build_connect_args_ipv4_enabled_with_sslmode(self, monkeypatch):
        # db_force_ipv4=True + db_sslmode="require" 동시 설정 시 두 키가 모두 포함되어야 한다
        _, db_mod = _reload_with_settings(
            monkeypatch, db_force_ipv4=True, db_sslmode="require"
        )
        fake_ipv4 = {"hostaddr": "1.2.3.4"}
        with patch.object(db_mod, "_ipv4_connect_args", return_value=fake_ipv4):
            result = db_mod._build_connect_args("postgresql://u:p@some-host/db")
        assert result.get("hostaddr") == "1.2.3.4"
        assert result.get("sslmode") == "require"

    def test_build_connect_args_sqlite_ignores_sslmode(self, monkeypatch):
        # SQLite URL에서는 db_sslmode 설정이 있어도 sslmode 키가 없어야 한다
        # (SQLite는 psycopg2 connect_args를 지원하지 않음)
        _, db_mod = _reload_with_settings(monkeypatch, db_sslmode="require")
        result = db_mod._build_connect_args("sqlite:///:memory:")
        # sslmode가 없거나, 있어도 SQLite 연결 시 무해해야 한다
        # 구현 선택에 따라 두 가지 중 하나: sslmode 미포함 or 포함 허용
        # 여기서는 SQLite hostname=None → sslmode 미포함을 기대한다
        assert "sslmode" not in result


# ---------------------------------------------------------------------------
# create_engine pool 파라미터 검증
# ---------------------------------------------------------------------------

class TestEnginePoolSettings:
    """엔진 pool 파라미터가 settings 값에 따라 올바르게 구성되는지 검증한다.

    Note: `from sqlalchemy import create_engine` 패턴에서는 importlib.reload 시
    patch("src.database.create_engine")이 덮어써진다. 대신 SQLAlchemy QueuePool의
    실제 속성을 조회하여 설정값 반영 여부를 검증한다.
    """

    def _reload_postgres(self, monkeypatch, **kwargs):
        """postgresql URL로 설정을 재로드한다."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost/db")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
        monkeypatch.setenv("DB_SSLMODE", "")
        monkeypatch.setenv("DB_FORCE_IPV4", "false")
        for k, v in kwargs.items():
            monkeypatch.setenv(k.upper(), str(v))

        import src.config as cfg
        importlib.reload(cfg)
        import src.database as db_mod
        importlib.reload(db_mod)
        return db_mod

    def test_engine_uses_pool_size(self, monkeypatch):
        # db_pool_size=7 설정 시 QueuePool 크기가 7이어야 한다
        monkeypatch.setenv("DB_POOL_SIZE", "7")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "10")
        monkeypatch.setenv("DB_POOL_TIMEOUT", "30")
        monkeypatch.setenv("DB_POOL_RECYCLE", "1800")
        db_mod = self._reload_postgres(monkeypatch)
        assert db_mod.engine.pool.size() == 7

    def test_engine_uses_max_overflow(self, monkeypatch):
        # db_max_overflow=15 설정 시 QueuePool의 overflow 상한이 15이어야 한다
        monkeypatch.setenv("DB_POOL_SIZE", "5")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "15")
        monkeypatch.setenv("DB_POOL_TIMEOUT", "30")
        monkeypatch.setenv("DB_POOL_RECYCLE", "1800")
        db_mod = self._reload_postgres(monkeypatch)
        assert db_mod.engine.pool._max_overflow == 15

    def test_engine_uses_pool_timeout(self, monkeypatch):
        # db_pool_timeout=45 설정 시 QueuePool timeout이 45이어야 한다
        monkeypatch.setenv("DB_POOL_SIZE", "5")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "10")
        monkeypatch.setenv("DB_POOL_TIMEOUT", "45")
        monkeypatch.setenv("DB_POOL_RECYCLE", "1800")
        db_mod = self._reload_postgres(monkeypatch)
        assert db_mod.engine.pool._timeout == 45

    def test_engine_uses_pool_recycle(self, monkeypatch):
        # db_pool_recycle=3600 설정 시 QueuePool recycle 시간이 3600이어야 한다
        monkeypatch.setenv("DB_POOL_SIZE", "5")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "10")
        monkeypatch.setenv("DB_POOL_TIMEOUT", "30")
        monkeypatch.setenv("DB_POOL_RECYCLE", "3600")
        db_mod = self._reload_postgres(monkeypatch)
        assert db_mod.engine.pool._recycle == 3600

    def test_engine_uses_all_pool_settings(self, monkeypatch):
        # 네 가지 pool 파라미터가 모두 QueuePool에 반영되어야 한다
        monkeypatch.setenv("DB_POOL_SIZE", "8")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "12")
        monkeypatch.setenv("DB_POOL_TIMEOUT", "20")
        monkeypatch.setenv("DB_POOL_RECYCLE", "900")
        db_mod = self._reload_postgres(monkeypatch)
        assert db_mod.engine.pool.size() == 8
        assert db_mod.engine.pool._max_overflow == 12
        assert db_mod.engine.pool._timeout == 20
        assert db_mod.engine.pool._recycle == 900
