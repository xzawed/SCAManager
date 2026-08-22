"""tests/test_database.py

src/database.py의 _build_connect_args() 함수와 engine pool 설정을 검증한다.
_build_connect_args는 Task 2 구현 전까지 존재하지 않으므로 현재 테스트는 실패(Red)해야 한다.
"""
import importlib
from unittest.mock import patch

import pytest


# conftest.py가 먼저 환경변수를 주입하므로 src import 전 추가 설정 불필요.
# 단, 각 테스트에서 settings를 재구성할 때 monkeypatch로 제어한다.


@pytest.fixture(autouse=True)
def _isolate_database_module(database_module_isolation):
    """이 파일은 `importlib.reload(src.database)` 를 쓰므로 격리를 **강제**한다.
    This module reloads src.database, so isolation is mandatory — not opt-in.

    autouse 인 이유: 신규 테스트 작성자가 fixture 요청을 잊으면 오염이 다시 샌다.
    그 누락이 #1102 회귀 가드를 **알파벳 순서 의존**으로 만들었다(2026-07-19 회고 B1).
    autouse because a forgotten fixture request is exactly how the leak returned before.
    """


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


# ─── 🔴 PostgreSQL 세션 타임존을 UTC 로 고정한다 ──────────────────────────────
#
# 이 저장소의 DateTime 컬럼은 전부 naive(`TIMESTAMP WITHOUT TIME ZONE`)이고,
# 모델 default 18곳(`default=` 15 + `onupdate=` 3)은 aware `datetime.now(timezone.utc)` 를
# 그 컬럼에 넣는다. psycopg2 는 aware 값을 timestamptz 로 보내고, PostgreSQL 은 그것을
# `timestamp` 로 캐스팅할 때 **세션 TimeZone** 을 쓴다. 세션이 UTC 가 아니면 저장값이
# 오프셋만큼 이동하고, 그 뒤의 모든 naive 비교(윈도우 경계·만료·보존 sweep)가 함께 어긋난다.
#
# `_build_connect_args` 에는 그 타임존을 고정하는 것이 없었다 — 서버/역할 기본값에 의존했다.
# SQLite 단위 테스트는 tzinfo 를 벗겨 이 축을 통째로 숨긴다.
#
# 값을 바꾸는 대신 **해석의 기준**을 고정한다: 기존에 저장된 행의 의미가 바뀌지 않는다.
# Pin the session TimeZone instead of rewriting 18 column defaults: existing rows keep meaning.

def test_postgres_connect_args_pin_the_session_timezone_to_utc(monkeypatch):
    """PostgreSQL URL 이면 `options` 로 세션 TimeZone 을 UTC 로 고정해야 한다."""
    _, db_mod = _reload_with_settings(monkeypatch)
    args = db_mod._build_connect_args("postgresql://u:p@localhost/db")

    options = args.get("options", "")
    assert "timezone" in options.lower(), (
        f"connect_args 에 세션 타임존 고정이 없다: {args!r} — 서버 기본값에 의존하면 "
        "aware default 18곳이 naive 컬럼에 오프셋만큼 이동해 저장된다."
    )
    assert "utc" in options.lower(), f"타임존이 UTC 가 아니다: {options!r}"


def test_sqlite_gets_no_libpq_options(monkeypatch):
    """대조축 — SQLite 는 libpq 인수를 받지 않는다. 넣으면 연결 자체가 깨진다."""
    _, db_mod = _reload_with_settings(monkeypatch)
    assert db_mod._build_connect_args("sqlite:///:memory:") == {}


def test_explicit_url_options_are_not_clobbered(monkeypatch):
    """URL query 가 이미 `options` 를 지정했으면 덮어쓰지 않는다.

    `sslmode` 와 같은 규칙이다(`_build_connect_args` docstring) — 운영자가 URL 에 적은
    값이 코드의 기본값에 조용히 지워지면, 그 사람은 자기가 설정한 것이 왜 안 먹는지
    알 수 없다. libpq 는 URL 의 `options` 와 connect_args 의 `options` 가 겹치면
    connect_args 를 쓴다.
    """
    _, db_mod = _reload_with_settings(monkeypatch)
    args = db_mod._build_connect_args(
        "postgresql://u:p@localhost/db?options=-c%20statement_timeout%3D5000"
    )
    assert "options" not in args, (
        f"URL 이 지정한 options 를 코드가 덮어쓴다: {args!r}"
    )
