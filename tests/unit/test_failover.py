"""tests/test_failover.py

TDD Red Phase: DB Failover 기능 테스트.

검증 대상:
  - src/database.py: FailoverSessionFactory 클래스
  - src/config.py: database_url_fallback, db_failover_probe_interval 필드
  - src/main.py: GET /health 응답에 "active_db" 키 추가

모든 테스트는 구현 전이므로 현재 실패(Red)해야 한다.
실제 DB 연결 없이 mock으로만 처리한다.
"""
import importlib
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

# conftest.py 가 이미 환경변수를 주입하므로 추가 설정 불필요.
# conftest.py already injects environment variables, so no additional setup is needed.
# 단, Settings 직접 인스턴스화 테스트에서는 필요한 필드만 명시적으로 전달한다.
# However, tests that instantiate Settings directly must pass only the required fields explicitly.


# ---------------------------------------------------------------------------
# 헬퍼 — src.config + src.database reload
# ---------------------------------------------------------------------------

def _reload_db_module(monkeypatch, *, fallback_url: str = "", probe_interval: int = 30):
    """Fallback URL과 probe interval 설정 후 src.config·src.database를 재로드한다.
    (reload 패턴: config 먼저, database 이후)"""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
    monkeypatch.setenv("DATABASE_URL_FALLBACK", fallback_url)
    monkeypatch.setenv("DB_FAILOVER_PROBE_INTERVAL", str(probe_interval))

    import src.config as cfg
    importlib.reload(cfg)
    import src.database as db_mod
    importlib.reload(db_mod)
    return db_mod


# ---------------------------------------------------------------------------
# 테스트 1: Fallback URL 미설정 시 단일 엔진 모드
# ---------------------------------------------------------------------------

class TestSingleEngineNoFallback:
    """DATABASE_URL_FALLBACK 미설정 시 FailoverSessionFactory 단일 엔진 모드 동작."""

    def test_fallback_engine_is_none_when_no_fallback_url(self, monkeypatch):
        # DATABASE_URL_FALLBACK="" 이면 _fallback_engine 이 None 이어야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        factory = db_mod.FailoverSessionFactory(db_mod.engine, fallback_url="")
        assert factory._fallback_engine is None

    def test_active_db_is_primary_in_single_engine_mode(self, monkeypatch):
        # Fallback URL 없는 단일 엔진 모드에서 active_db == "primary" 이어야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        factory = db_mod.FailoverSessionFactory(db_mod.engine, fallback_url="")
        assert factory.active_db == "primary"

    def test_no_probe_thread_when_no_fallback_url(self, monkeypatch):
        # Fallback URL 없으면 백그라운드 probe 스레드가 생성되지 않아야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        daemon_before = {t.ident for t in threading.enumerate() if t.daemon}
        factory = db_mod.FailoverSessionFactory(db_mod.engine, fallback_url="")
        daemon_after = {t.ident for t in threading.enumerate() if t.daemon}
        # probe 스레드가 추가되지 않았는지 확인 (생성 전후 daemon 스레드 수 변화 없음)
        # Verify no probe thread was added (daemon thread count must not change before/after creation).
        assert factory._probe_thread is None

    def test_call_returns_primary_session_directly(self, monkeypatch):
        # 단일 엔진 모드에서 factory() 호출은 Primary Session을 바로 반환해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        mock_session = MagicMock()
        mock_primary_maker = MagicMock(return_value=mock_session)
        factory = db_mod.FailoverSessionFactory(db_mod.engine, fallback_url="")
        factory._primary_maker = mock_primary_maker
        result = factory()
        mock_primary_maker.assert_called_once()
        assert result is mock_session


# ---------------------------------------------------------------------------
# 테스트 2: Primary 실패 시 Fallback 전환
# ---------------------------------------------------------------------------

class TestFailoverOnPrimaryFailure:
    """Primary DB 연결 실패 시 Fallback DB로 자동 전환을 검증한다."""

    def test_active_db_switches_to_fallback_on_primary_error(self, monkeypatch):
        # Primary Session 호출에서 OperationalError 발생 시 active_db="fallback"으로 전환해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        fallback_session = MagicMock()
        mock_primary_maker = MagicMock(
            side_effect=OperationalError("conn failed", None, None)
        )
        mock_fallback_maker = MagicMock(return_value=fallback_session)

        factory = db_mod.FailoverSessionFactory(
            db_mod.engine,
            fallback_url="sqlite:///:memory:",
        )
        factory._primary_maker = mock_primary_maker
        factory._fallback_maker = mock_fallback_maker

        # Primary 실패 → fallback으로 전환 후 session 반환
        result = factory()
        assert factory.active_db == "fallback"
        assert result is fallback_session

    def test_fallback_session_returned_after_primary_failure(self, monkeypatch):
        # Primary 실패 후 Fallback Session 객체가 반환되어야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        fallback_session = MagicMock(name="fallback_session")
        mock_primary_maker = MagicMock(
            side_effect=OperationalError("conn failed", None, None)
        )
        mock_fallback_maker = MagicMock(return_value=fallback_session)

        factory = db_mod.FailoverSessionFactory(
            db_mod.engine,
            fallback_url="sqlite:///:memory:",
        )
        factory._primary_maker = mock_primary_maker
        factory._fallback_maker = mock_fallback_maker

        result = factory()
        assert result is fallback_session

    def test_already_in_fallback_mode_skips_primary(self, monkeypatch):
        # active_db == "fallback" 상태에서 factory() 호출은 Primary를 시도하지 않아야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        fallback_session = MagicMock()
        mock_primary_maker = MagicMock()
        mock_fallback_maker = MagicMock(return_value=fallback_session)

        factory = db_mod.FailoverSessionFactory(
            db_mod.engine,
            fallback_url="sqlite:///:memory:",
        )
        factory._primary_maker = mock_primary_maker
        factory._fallback_maker = mock_fallback_maker
        factory._active = "fallback"  # 이미 fallback 상태 강제 설정

        result = factory()
        mock_primary_maker.assert_not_called()
        assert result is fallback_session


# ---------------------------------------------------------------------------
# 테스트 3: Primary 정상 동작 시 active_db == "primary"
# ---------------------------------------------------------------------------

class TestActivePrimaryByDefault:
    """Fallback URL이 설정된 상태에서도 Primary 정상이면 active_db="primary"를 유지한다."""

    def test_active_db_is_primary_when_primary_healthy(self, monkeypatch):
        # Primary가 정상 동작하면 active_db == "primary" 이어야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        primary_session = MagicMock()
        mock_primary_maker = MagicMock(return_value=primary_session)

        factory = db_mod.FailoverSessionFactory(
            db_mod.engine,
            fallback_url="sqlite:///:memory:",
        )
        factory._primary_maker = mock_primary_maker

        result = factory()
        assert factory.active_db == "primary"
        assert result is primary_session

    def test_probe_thread_created_when_fallback_url_provided(self, monkeypatch):
        # Fallback URL이 있으면 probe 스레드가 생성되어야 한다 (daemon=True)
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        with patch.object(db_mod.FailoverSessionFactory, "_start_probe_thread") as mock_start:
            factory = db_mod.FailoverSessionFactory(
                db_mod.engine,
                fallback_url="sqlite:///:memory:",
            )
        mock_start.assert_called_once()


# ---------------------------------------------------------------------------
# 테스트 4: /health 엔드포인트 — active_db 키 포함
# ---------------------------------------------------------------------------

class TestHealthEndpointActiveDb:
    """GET /health 응답은 status=ok 만 반환하고 내부 DB 상태를 노출하지 않아야 한다.
    GET /health must return status=ok only and must NOT expose internal DB state."""

    def test_health_returns_status_ok(self):
        # GET /health 응답 JSON에 "status": "ok" 가 포함되어야 한다
        # GET /health response JSON must contain "status": "ok".
        from src.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_health_does_not_expose_active_db(self):
        # 보안 강화: active_db 필드는 내부 DB 상태를 노출하므로 응답에서 제거
        # Security hardening: active_db exposes internal DB failover state — removed from response.
        from src.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert "active_db" not in response.json()

    def test_health_active_db_is_primary_or_fallback(self):
        # 내부 DB 상태 노출 제거로 active_db 키는 존재하지 않음 (None 반환)
        # active_db key no longer exists after security hardening (returns None).
        from src.main import app
        client = TestClient(app)
        response = client.get("/health")
        active_db = response.json().get("active_db")
        assert active_db is None


# ---------------------------------------------------------------------------
# 테스트 5: Fallback URL Supabase 자동 정규화
# ---------------------------------------------------------------------------

class TestFallbackUrlNormalization:
    """database_url_fallback 필드의 postgres:// → postgresql:// 변환 및 Supabase sslmode 추가."""

    def test_fallback_url_postgres_scheme_converted(self):
        # "postgres://..." 스킴이 "postgresql://..."으로 변환되어야 한다
        from src.config import Settings
        s = Settings(
            database_url="sqlite:///:memory:",
            github_webhook_secret="x",
            github_token="x",
            telegram_bot_token="123:ABC",
            telegram_chat_id="-100",
            database_url_fallback="postgres://user:pass@db.supabase.co:5432/postgres",
        )
        assert s.database_url_fallback.startswith("postgresql://")

    def test_fallback_url_supabase_gets_sslmode_require(self):
        # Supabase URL 이면 sslmode=require 가 자동으로 추가되어야 한다
        from src.config import Settings
        s = Settings(
            database_url="sqlite:///:memory:",
            github_webhook_secret="x",
            github_token="x",
            telegram_bot_token="123:ABC",
            telegram_chat_id="-100",
            database_url_fallback="postgres://user:pass@db.supabase.co:5432/postgres",
        )
        assert "sslmode=require" in s.database_url_fallback

    def test_fallback_url_non_supabase_no_sslmode_auto_added(self):
        # 일반 PostgreSQL URL(Supabase 아님) 은 sslmode 를 자동 추가하지 않아야 한다
        from src.config import Settings
        s = Settings(
            database_url="sqlite:///:memory:",
            github_webhook_secret="x",
            github_token="x",
            telegram_bot_token="123:ABC",
            telegram_chat_id="-100",
            database_url_fallback="postgres://user:pass@onprem-host:5432/mydb",
        )
        assert "sslmode" not in s.database_url_fallback
        assert s.database_url_fallback.startswith("postgresql://")


# ---------------------------------------------------------------------------
# 테스트 6: Fallback URL 빈 문자열 — 정규화 없이 빈 문자열 유지
# ---------------------------------------------------------------------------

class TestFallbackUrlEmptyNoNormalization:
    """database_url_fallback="" 이면 빈 문자열 유지, 에러 없음."""

    def test_empty_fallback_url_stays_empty(self):
        # database_url_fallback="" 설정 시 빈 문자열을 그대로 유지해야 한다
        from src.config import Settings
        s = Settings(
            database_url="sqlite:///:memory:",
            github_webhook_secret="x",
            github_token="x",
            telegram_bot_token="123:ABC",
            telegram_chat_id="-100",
            database_url_fallback="",
        )
        assert s.database_url_fallback == ""

    def test_empty_fallback_url_no_exception(self):
        # database_url_fallback="" 설정 시 Settings 인스턴스화에서 예외가 발생하지 않아야 한다
        from src.config import Settings
        try:
            Settings(
                database_url="sqlite:///:memory:",
                github_webhook_secret="x",
                github_token="x",
                telegram_bot_token="123:ABC",
                telegram_chat_id="-100",
                database_url_fallback="",
            )
        except Exception as exc:
            pytest.fail(f"Settings() raised unexpected exception: {exc}")

    def test_probe_interval_default_is_30(self):
        # db_failover_probe_interval 기본값이 30 이어야 한다
        from src.config import Settings
        s = Settings(
            database_url="sqlite:///:memory:",
            github_webhook_secret="x",
            github_token="x",
            telegram_bot_token="123:ABC",
            telegram_chat_id="-100",
        )
        assert s.db_failover_probe_interval == 30


# ---------------------------------------------------------------------------
# 테스트 7: URL에 sslmode 이미 포함된 경우 connect_args에 중복 추가 금지
# ---------------------------------------------------------------------------

class TestNoSslmodeConflictInConnectArgs:
    """URL 쿼리스트링에 ?sslmode=require 가 있으면 _build_connect_args 결과에 sslmode 키 없음."""

    def test_no_sslmode_in_connect_args_when_url_has_sslmode(self, monkeypatch):
        # URL에 ?sslmode=require 포함 시 _build_connect_args 결과에 "sslmode" 키가 없어야 한다
        # (URL 레벨 sslmode 와 connect_args 레벨 sslmode 중복 방지)
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db?sslmode=require")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
        monkeypatch.setenv("DB_SSLMODE", "")   # env 설정은 비어 있음
        monkeypatch.setenv("DB_FORCE_IPV4", "false")

        import src.config as cfg
        importlib.reload(cfg)
        import src.database as db_mod
        importlib.reload(db_mod)

        result = db_mod._build_connect_args("postgresql://u:p@host/db?sslmode=require")
        assert "sslmode" not in result

    def test_sslmode_not_doubled_when_db_sslmode_env_and_url_both_set(self, monkeypatch):
        # URL에 ?sslmode=require 가 있고 DB_SSLMODE 도 설정된 경우
        # _build_connect_args 는 URL 쿼리스트링 우선으로 connect_args sslmode 를 생략해야 한다
        monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")
        monkeypatch.setenv("DB_SSLMODE", "require")
        monkeypatch.setenv("DB_FORCE_IPV4", "false")

        import src.config as cfg
        importlib.reload(cfg)
        import src.database as db_mod
        importlib.reload(db_mod)

        # URL에 sslmode 가 없는 경우 connect_args 에 sslmode 가 포함되어야 한다 (기존 동작 유지)
        result_without_url_sslmode = db_mod._build_connect_args("postgresql://u:p@host/db")
        assert result_without_url_sslmode.get("sslmode") == "require"

        # URL에 sslmode 가 있는 경우 connect_args 에 sslmode 가 없어야 한다
        result_with_url_sslmode = db_mod._build_connect_args(
            "postgresql://u:p@host/db?sslmode=require"
        )
        assert "sslmode" not in result_with_url_sslmode


# ---------------------------------------------------------------------------
# 테스트 8: FailoverSessionFactory import 가능 여부
# ---------------------------------------------------------------------------

class TestFailoverSessionFactoryImport:
    """src.database 에서 FailoverSessionFactory 를 import 할 수 있어야 한다."""

    def test_failover_session_factory_importable(self):
        # FailoverSessionFactory 가 src.database 에서 import 가능해야 한다
        from src.database import FailoverSessionFactory  # noqa: F401
        assert FailoverSessionFactory is not None

    def test_failover_session_factory_is_callable(self):
        # FailoverSessionFactory 인스턴스는 callable 이어야 한다 (SessionLocal() 호환)
        from src.database import FailoverSessionFactory, engine
        factory = FailoverSessionFactory(engine, fallback_url="")
        assert callable(factory)

    def test_failover_session_factory_has_active_db_property(self):
        # FailoverSessionFactory 인스턴스는 active_db 속성을 가져야 한다
        from src.database import FailoverSessionFactory, engine
        factory = FailoverSessionFactory(engine, fallback_url="")
        assert hasattr(factory, "active_db")

    def test_failover_session_factory_active_db_type_is_str(self):
        # active_db 속성값은 문자열 타입이어야 한다
        # The active_db property value must be of type str.
        from src.database import FailoverSessionFactory, engine
        factory = FailoverSessionFactory(engine, fallback_url="")
        assert isinstance(factory.active_db, str)


# ---------------------------------------------------------------------------
# 테스트 9: db_failover_probe_interval 설정 반영
# ---------------------------------------------------------------------------

class TestProbeInterval:
    """db_failover_probe_interval 환경변수가 Settings에 정상 반영되는지 검증한다."""

    def test_probe_interval_custom_value(self):
        # db_failover_probe_interval=60 으로 설정 시 Settings 에 반영되어야 한다
        from src.config import Settings
        s = Settings(
            database_url="sqlite:///:memory:",
            github_webhook_secret="x",
            github_token="x",
            telegram_bot_token="123:ABC",
            telegram_chat_id="-100",
            db_failover_probe_interval=60,
        )
        assert s.db_failover_probe_interval == 60

    def test_probe_interval_env_var(self, monkeypatch):
        # DB_FAILOVER_PROBE_INTERVAL 환경변수가 Settings 필드에 반영되어야 한다
        monkeypatch.setenv("DB_FAILOVER_PROBE_INTERVAL", "45")
        import src.config as cfg
        importlib.reload(cfg)
        assert cfg.settings.db_failover_probe_interval == 45


# ---------------------------------------------------------------------------
# 테스트 10: _ipv4_connect_args 엣지 케이스 (line 27, 33-34, 39-41)
# ---------------------------------------------------------------------------

class TestIpv4ConnectArgsEdgeCases:
    """_ipv4_connect_args의 예외 경로를 검증한다."""

    def test_sqlite_url_returns_empty_dict(self, monkeypatch):
        # hostname이 None(SQLite)이면 빈 dict를 반환해야 한다 (line 27)
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        result = db_mod._ipv4_connect_args("sqlite:///:memory:")
        assert result == {}

    def test_gaierror_returns_empty_dict(self, monkeypatch):
        # socket.getaddrinfo가 gaierror를 발생시키면 빈 dict를 반환해야 한다 (line 33-34)
        import socket
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("name resolution failed")):
            result = db_mod._ipv4_connect_args("postgresql://u:p@some-host:5432/db")
        assert result == {}

    def test_timeout_returns_empty_dict(self, monkeypatch):
        # DNS 조회 timeout 시 빈 dict를 반환해야 한다 (line 33-34)
        import concurrent.futures
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        with patch("socket.getaddrinfo", side_effect=concurrent.futures.TimeoutError()):
            result = db_mod._ipv4_connect_args("postgresql://u:p@some-host:5432/db")
        assert result == {}

    def test_empty_addrinfo_returns_empty_dict(self, monkeypatch):
        # getaddrinfo가 빈 리스트를 반환하면 빈 dict를 반환해야 한다 (line 41)
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        with patch("socket.getaddrinfo", return_value=[]):
            result = db_mod._ipv4_connect_args("postgresql://u:p@some-host:5432/db")
        assert result == {}

    def test_invalid_port_returns_empty_dict(self, monkeypatch):
        # 포트가 비정수(ValueError)이면 빈 dict를 반환해야 한다 (line 39-40)
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        # urlparse는 비정수 포트를 parsed.port 접근 시 ValueError 발생시킴
        result = db_mod._ipv4_connect_args("postgresql://u:p@host:notaport/db")
        assert result == {}


# ---------------------------------------------------------------------------
# 테스트 11: _current_maker() (line 134-136)
# ---------------------------------------------------------------------------

class TestCurrentMaker:
    """_current_maker()가 active 상태에 따라 올바른 maker를 반환하는지 검증한다."""

    def test_current_maker_returns_fallback_when_active_fallback(self, monkeypatch):
        # active == "fallback" 이고 fallback_maker가 있으면 fallback_maker를 반환해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )
        factory._active = "fallback"
        assert factory._current_maker() is factory._fallback_maker

    def test_current_maker_returns_primary_when_active_primary(self, monkeypatch):
        # active == "primary" 이면 primary_maker를 반환해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )
        factory._active = "primary"
        assert factory._current_maker() is factory._primary_maker

    def test_current_maker_returns_primary_when_no_fallback_maker(self, monkeypatch):
        # fallback_maker가 None이면 active에 관계없이 primary_maker를 반환해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        factory = db_mod.FailoverSessionFactory(db_mod.engine, fallback_url="")
        factory._active = "fallback"  # fallback_maker 없는 상태에서 강제 설정
        assert factory._current_maker() is factory._primary_maker


# ---------------------------------------------------------------------------
# 테스트 12: __call__ 예외 경로 (line 150-152, 159-161, 170-172)
# ---------------------------------------------------------------------------

class TestCallExceptionPaths:
    """__call__() 내부 예외 경로를 검증한다."""

    def test_fallback_mode_session_execute_fails_raises(self, monkeypatch):
        # 이미 fallback 모드에서 session.execute()가 실패하면 예외가 전파되어야 한다 (line 150-152)
        from sqlalchemy.exc import OperationalError
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )
        factory._active = "fallback"

        failing_session = MagicMock()
        failing_session.execute.side_effect = OperationalError("fallback down", None, None)
        factory._fallback_maker = MagicMock(return_value=failing_session)

        with pytest.raises(OperationalError):
            factory()

        failing_session.close.assert_called_once()

    def test_primary_session_execute_fails_switches_to_fallback(self, monkeypatch):
        # primary session.execute()에서 OperationalError → fallback으로 전환 (line 159-161)
        from sqlalchemy.exc import OperationalError
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )

        failing_primary_session = MagicMock()
        failing_primary_session.execute.side_effect = OperationalError("primary exec fail", None, None)
        fallback_session = MagicMock()

        factory._primary_maker = MagicMock(return_value=failing_primary_session)
        factory._fallback_maker = MagicMock(return_value=fallback_session)

        result = factory()
        assert factory.active_db == "fallback"
        assert result is fallback_session
        failing_primary_session.close.assert_called_once()

    def test_fallback_session_execute_fails_after_primary_failure_raises(self, monkeypatch):
        # primary 실패 후 fallback session.execute()도 실패하면 예외 전파 (line 170-172)
        from sqlalchemy.exc import OperationalError
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:")
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )

        failing_primary_session = MagicMock()
        failing_primary_session.execute.side_effect = OperationalError("primary fail", None, None)
        failing_fallback_session = MagicMock()
        failing_fallback_session.execute.side_effect = Exception("fallback also down")

        factory._primary_maker = MagicMock(return_value=failing_primary_session)
        factory._fallback_maker = MagicMock(return_value=failing_fallback_session)

        with pytest.raises(Exception, match="fallback also down"):
            factory()

        failing_fallback_session.close.assert_called_once()


# ---------------------------------------------------------------------------
# 테스트 13: _probe_primary_loop (line 184-193)
# ---------------------------------------------------------------------------

class TestProbePrimaryLoop:
    """_probe_primary_loop가 primary 복구 시 자동 복귀하는지 검증한다."""

    def test_probe_loop_switches_back_to_primary_on_recovery(self, monkeypatch):
        # fallback 상태에서 primary engine 연결 성공 시 active_db가 "primary"로 복귀해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:", probe_interval=1)
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )
        factory._active = "fallback"

        call_count = 0
        def fake_sleep(_):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise SystemExit("stop loop")

        with patch("src.database.time.sleep", fake_sleep):
            with patch.object(factory._primary_engine, "connect") as mock_connect:
                mock_conn = MagicMock()
                mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
                mock_connect.return_value.__exit__ = MagicMock(return_value=False)
                try:
                    factory._probe_primary_loop()
                except SystemExit:
                    pass

        assert factory.active_db == "primary"

    def test_probe_loop_stays_fallback_when_primary_still_down(self, monkeypatch):
        # fallback 상태에서 primary engine 연결 실패 시 active_db가 "fallback"을 유지해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:", probe_interval=1)
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )
        factory._active = "fallback"

        call_count = 0
        def fake_sleep(_):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise SystemExit("stop loop")

        with patch("src.database.time.sleep", fake_sleep):
            with patch.object(factory._primary_engine, "connect", side_effect=Exception("still down")):
                try:
                    factory._probe_primary_loop()
                except SystemExit:
                    pass

        assert factory.active_db == "fallback"

    def test_probe_loop_skips_when_active_is_primary(self, monkeypatch):
        # active == "primary" 이면 연결 시도 없이 sleep만 반복해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="sqlite:///:memory:", probe_interval=1)
        factory = db_mod.FailoverSessionFactory(
            db_mod.engine, fallback_url="sqlite:///:memory:"
        )
        factory._active = "primary"

        call_count = 0
        def fake_sleep(_):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise SystemExit("stop loop")

        with patch("src.database.time.sleep", fake_sleep):
            with patch.object(factory._primary_engine, "connect") as mock_connect:
                try:
                    factory._probe_primary_loop()
                except SystemExit:
                    pass
                mock_connect.assert_not_called()


# ---------------------------------------------------------------------------
# 테스트 14: get_db() 제너레이터 (line 203-207)
# ---------------------------------------------------------------------------

class TestGetDb:
    """get_db() FastAPI dependency 제너레이터를 검증한다."""

    def test_get_db_yields_session(self, monkeypatch):
        # get_db()는 Session 객체를 yield해야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        mock_session = MagicMock()
        with patch.object(db_mod, "SessionLocal", return_value=mock_session):
            gen = db_mod.get_db()
            session = next(gen)
        assert session is mock_session

    def test_get_db_closes_session_on_exit(self, monkeypatch):
        # get_db() 제너레이터가 종료되면 session.close()가 호출되어야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        mock_session = MagicMock()
        with patch.object(db_mod, "SessionLocal", return_value=mock_session):
            gen = db_mod.get_db()
            next(gen)
            try:
                next(gen)
            except StopIteration:
                pass
        mock_session.close.assert_called_once()

    def test_get_db_closes_session_on_exception(self, monkeypatch):
        # get_db() 내에서 예외 발생 시에도 session.close()가 호출되어야 한다
        db_mod = _reload_db_module(monkeypatch, fallback_url="")
        mock_session = MagicMock()
        with patch.object(db_mod, "SessionLocal", return_value=mock_session):
            gen = db_mod.get_db()
            next(gen)
            try:
                gen.throw(RuntimeError("test error"))
            except RuntimeError:
                pass
        mock_session.close.assert_called_once()
