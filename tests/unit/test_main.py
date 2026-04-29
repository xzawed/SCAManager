"""Tests for src/main.py — FastAPI app entry point, lifespan, and route registration."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    # lifespan 없이 일반 요청 테스트용 — TestClient 단순 래핑
    return TestClient(app)


# --- /health 엔드포인트 ---

def test_health_returns_200(client):
    # GET /health 가 HTTP 200 을 반환하는지 검증
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok(client):
    # GET /health 응답 body 가 status=ok 를 포함하고 내부 구현 필드(active_db)는 노출하지 않는지 검증
    # Verify /health returns status=ok and does NOT expose internal fields (active_db).
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert "active_db" not in data  # 정보 노출 방지 — internal DB state must not be exposed


def test_health_security_headers(client):
    # 보안 헤더 미들웨어가 모든 응답에 X-Content-Type-Options 를 추가하는지 검증
    # Verify SecurityHeadersMiddleware adds X-Content-Type-Options to all responses.
    response = client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"


def test_health_tools_removed(client):
    # /health/tools 디버그 엔드포인트가 제거되어 404 를 반환하는지 검증
    # Verify the /health/tools debug endpoint is removed and returns 404.
    response = client.get("/health/tools")
    assert response.status_code == 404


# --- 라우트 등록 검증 ---
# --- Route registration verification ---

def test_health_route_is_registered():
    # /health 경로가 app.routes 에 등록되어 있는지 검증
    paths = [r.path for r in app.routes]
    assert "/health" in paths


def test_webhooks_route_is_registered():
    # /webhooks/github 경로가 app.routes 에 등록되어 있는지 검증
    paths = [r.path for r in app.routes]
    assert "/webhooks/github" in paths


# --- lifespan 동작 검증 ---

def test_lifespan_calls_run_migrations():
    # lifespan startup 시 _run_migrations 가 정확히 1회 호출되는지 검증
    with patch("src.main._run_migrations") as mock_migrate:
        with TestClient(app):
            pass
    mock_migrate.assert_called_once()


def test_lifespan_timeout_does_not_crash():
    # _run_migrations 에서 asyncio.TimeoutError 가 발생해도 앱이 정상 기동되는지 검증
    with patch("src.main._run_migrations", side_effect=TimeoutError):
        with TestClient(app) as c:
            response = c.get("/health")
    assert response.status_code == 200


def test_lifespan_exception_does_not_crash():
    # _run_migrations 에서 일반 Exception 이 발생해도 앱이 정상 기동되는지 검증
    with patch("src.main._run_migrations", side_effect=RuntimeError("db error")):
        with TestClient(app) as c:
            response = c.get("/health")
    assert response.status_code == 200


# --- ANTHROPIC_API_KEY 부재 경고 ---

def test_lifespan_warns_when_anthropic_key_missing(caplog):
    # settings.anthropic_api_key 가 빈 값이면 lifespan 시작 시 경고 로그가 남는지 검증
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = ""
        mock_settings.app_base_url = ""
        mock_settings.token_encryption_key = ""
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app):
                pass
    assert any("ANTHROPIC_API_KEY" in rec.message for rec in caplog.records), \
        "ANTHROPIC_API_KEY 부재 경고가 로그에 남지 않았습니다"


def test_lifespan_no_warning_when_anthropic_key_set(caplog):
    # settings.anthropic_api_key 가 설정되어 있으면 경고 로그가 남지 않아야 함
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = ""
        mock_settings.token_encryption_key = ""
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app):
                pass
    assert not any("ANTHROPIC_API_KEY" in rec.message for rec in caplog.records), \
        "키가 설정되어 있는데도 경고 로그가 남았습니다"


# --- TOKEN_ENCRYPTION_KEY 부재 경고 (prod 환경) ---

def test_lifespan_warns_token_encryption_key_missing_in_prod(caplog):
    """prod 환경(https URL)에서 TOKEN_ENCRYPTION_KEY 미설정 시 SECURITY 경고 출력."""
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "https://scamanager.example.com"
        mock_settings.token_encryption_key = ""
        # Phase 2: strict 모드 비활성 (기본값) — warning 만 출력
        # Phase 2: strict mode disabled (default) — emits warning only
        mock_settings.strict_token_encryption = False
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app):
                pass
    assert any("TOKEN_ENCRYPTION_KEY" in rec.message for rec in caplog.records), \
        "prod 환경에서 TOKEN_ENCRYPTION_KEY 부재 경고가 로그에 남지 않았습니다"


def test_lifespan_no_warning_token_encryption_key_set_in_prod(caplog):
    """prod 환경이라도 TOKEN_ENCRYPTION_KEY 가 설정되어 있으면 경고 없음."""
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "https://scamanager.example.com"
        mock_settings.token_encryption_key = "some-valid-fernet-key-value"
        mock_settings.strict_token_encryption = False
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app):
                pass
    assert not any("TOKEN_ENCRYPTION_KEY" in rec.message for rec in caplog.records), \
        "키가 설정되어 있는데도 TOKEN_ENCRYPTION_KEY 경고가 남았습니다"


def test_lifespan_no_warning_token_encryption_key_dev_env(caplog):
    """dev 환경(http URL 또는 빈 URL)에서는 키가 없어도 경고 없음."""
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "http://localhost:8000"
        mock_settings.token_encryption_key = ""
        mock_settings.strict_token_encryption = False
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app):
                pass
    assert not any("TOKEN_ENCRYPTION_KEY" in rec.message for rec in caplog.records), \
        "dev(http) 환경에서 TOKEN_ENCRYPTION_KEY 경고가 남았습니다"


def test_lifespan_strict_mode_raises_when_key_missing_in_prod():
    """Phase 2: STRICT_TOKEN_ENCRYPTION=true 이고 prod (https) + 키 미설정 시 lifespan 차단.
    Phase 2: lifespan refuses to start when strict mode is on, prod env, and key empty.
    """
    import pytest
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "https://scamanager.example.com"
        mock_settings.token_encryption_key = ""
        mock_settings.strict_token_encryption = True  # 신규 모드 활성
        with pytest.raises(RuntimeError, match="STRICT_TOKEN_ENCRYPTION"):
            with TestClient(app):
                pass


def test_lifespan_strict_mode_skipped_in_dev_env():
    """Phase 2: dev (http) 환경에서는 strict 모드여도 차단 안 함 (prod 한정)."""
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "http://localhost:8000"
        mock_settings.token_encryption_key = ""
        mock_settings.strict_token_encryption = True
        # 차단 없이 정상 진행
        with TestClient(app):
            pass


def test_lifespan_strict_mode_passes_when_key_set():
    """Phase 2: strict 모드여도 키가 설정되어 있으면 정상 진행."""
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "https://scamanager.example.com"
        mock_settings.token_encryption_key = "valid-fernet-key"
        mock_settings.strict_token_encryption = True
        with TestClient(app):
            pass
