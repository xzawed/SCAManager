"""Tests for src/main.py — FastAPI app entry point, lifespan, and route registration."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from tests.unit._route_helpers import registered_paths


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
    # /health 경로가 등록되어 있는지 검증
    # Verify the /health route is registered.
    assert "/health" in registered_paths(app)


def test_webhooks_route_is_registered():
    # /webhooks/github 경로가 등록되어 있는지 검증
    # Verify the /webhooks/github route is registered.
    assert "/webhooks/github" in registered_paths(app)


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


# --- Phase 2 PR #113: STRICT_TOKEN_ENCRYPTION fail-fast ---

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


# --- Phase 2 PR #112: GitHub API warmup ping ---

def test_lifespan_warmup_ping_logs_success(caplog):
    """Phase 2: lifespan warmup ping 성공 시 INFO 로그.
    Phase 2: lifespan warmup ping logs INFO on success.
    """
    import logging as _logging
    from unittest.mock import AsyncMock

    mock_client = AsyncMock()
    mock_client.get = AsyncMock()  # 성공
    with patch("src.main._run_migrations"), \
         patch("src.shared.http_client.get_http_client", return_value=mock_client):
        with caplog.at_level(_logging.INFO, logger="src.main"):
            with TestClient(app):
                pass
    assert any(
        "GitHub API warm-up ping succeeded" in rec.message
        for rec in caplog.records
    ), "warmup 성공 INFO 로그가 남지 않았습니다"
    mock_client.get.assert_awaited()


def test_lifespan_warmup_ping_handles_failure_silently(caplog):
    """Phase 2: lifespan warmup ping 실패 시 INFO 로그 + 앱 정상 기동 (best-effort).
    Phase 2: warmup failure logs INFO and the app still starts up normally.
    """
    import logging as _logging
    from unittest.mock import AsyncMock

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=RuntimeError("network unreachable"))
    with patch("src.main._run_migrations"), \
         patch("src.shared.http_client.get_http_client", return_value=mock_client):
        with caplog.at_level(_logging.INFO, logger="src.main"):
            with TestClient(app) as c:
                resp = c.get("/health")
    # 앱 정상 기동
    assert resp.status_code == 200
    # warmup 스킵 INFO 로그
    assert any(
        "GitHub API warm-up ping skipped" in rec.message
        for rec in caplog.records
    ), "warmup 실패 INFO 로그가 남지 않았습니다"


# --- PR-4 G1: StaticFiles `/static/vendor/chart.umd.min.js` 200 응답 가드 ---
# UI 감사 Step C 회귀 가드 — Chart.js vendoring 이 정상 마운트됐는지 확인
# UI audit Step C regression guard — verify Chart.js is correctly mounted

# --- TELEGRAM_WEBHOOK_SECRET 부재 경고 (prod 환경) ---
# --- TELEGRAM_WEBHOOK_SECRET absence warning (prod environment) ---

def test_lifespan_warns_telegram_webhook_secret_missing_in_prod(caplog):
    """prod 환경(https URL)에서 TELEGRAM_WEBHOOK_SECRET 미설정 시 SECURITY 경고 출력.
    Warns when TELEGRAM_WEBHOOK_SECRET is unset in production — /webhooks/telegram auth bypassed.
    """
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "https://scamanager.example.com"
        mock_settings.token_encryption_key = "valid-fernet-key"
        mock_settings.strict_token_encryption = False
        mock_settings.telegram_webhook_secret = ""
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app):
                pass
    assert any("TELEGRAM_WEBHOOK_SECRET" in rec.message for rec in caplog.records), \
        "prod 환경에서 TELEGRAM_WEBHOOK_SECRET 부재 경고가 로그에 남지 않았습니다"


def test_lifespan_no_warning_telegram_webhook_secret_set_in_prod(caplog):
    """prod 환경이라도 TELEGRAM_WEBHOOK_SECRET 가 설정되어 있으면 경고 없음.
    No warning when TELEGRAM_WEBHOOK_SECRET is set — authentication is active.
    """
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "https://scamanager.example.com"
        mock_settings.token_encryption_key = "valid-fernet-key"
        mock_settings.strict_token_encryption = False
        mock_settings.telegram_webhook_secret = "some-secret-token"
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app) as c:
                c.get("/health")
    assert not any("TELEGRAM_WEBHOOK_SECRET" in rec.message for rec in caplog.records), \
        "시크릿이 설정되어 있는데도 TELEGRAM_WEBHOOK_SECRET 경고가 남았습니다"


def test_lifespan_no_warning_telegram_webhook_secret_dev_env(caplog):
    """dev 환경(http URL)에서는 시크릿이 없어도 경고 없음 — prod 전용 체크.
    No warning in dev (http) environments — the check is prod-only.
    """
    import logging as _logging
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "test-session-secret-32-chars-long!"
        mock_settings.anthropic_api_key = "sk-ant-test-key"
        mock_settings.app_base_url = "http://localhost:8000"
        mock_settings.token_encryption_key = ""
        mock_settings.strict_token_encryption = False
        mock_settings.telegram_webhook_secret = ""
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app) as c:
                c.get("/health")
    assert not any("TELEGRAM_WEBHOOK_SECRET" in rec.message for rec in caplog.records), \
        "dev(http) 환경에서 TELEGRAM_WEBHOOK_SECRET 경고가 남았습니다"


# --- PR-4 G1: StaticFiles `/static/vendor/chart.umd.min.js` 200 응답 가드 ---
# UI 감사 Step C 회귀 가드 — Chart.js vendoring 이 정상 마운트됐는지 확인
# UI audit Step C regression guard — verify Chart.js is correctly mounted

def test_static_chartjs_returns_200(client):
    """StaticFiles `/static/vendor/chart.umd.min.js` 가 200 + JS Content-Type 반환.
    Verify vendored Chart.js is served successfully.

    회귀 위험: src/main.py 의 app.mount('/static', StaticFiles(...)) 가 실수로
    제거되거나 src/static/vendor/chart.umd.min.js 가 git history 에서 사라질 때 차단.
    Regression guard: blocks accidental removal of mount or vendored asset.
    """
    response = client.get("/static/vendor/chart.umd.min.js")
    assert response.status_code == 200, (
        f"Chart.js vendored 자원 응답 실패: {response.status_code} "
        f"— src/main.py StaticFiles mount 또는 src/static/vendor/chart.umd.min.js 누락"
    )
    # 파일 크기 sanity check (Chart.js 4.4.0 UMD min 약 200KB)
    # File size sanity check (~200KB for Chart.js 4.4.0 UMD min)
    assert len(response.content) > 100_000, (
        f"Chart.js 파일 크기 비정상: {len(response.content)} bytes (200KB+ 기대)"
    )
    # UMD 시그니처 확인 — 첫 부분에 Chart.js 라이선스 주석 포함
    # UMD signature check — Chart.js license header in the first bytes
    head = response.content[:200]
    assert b"Chart.js" in head, "Chart.js UMD 시그니처 누락 — 다른 파일이 마운트됨"


def test_static_missing_file_returns_404(client):
    """존재하지 않는 static 자원은 404 반환 (graceful)."""
    response = client.get("/static/vendor/nonexistent.js")
    assert response.status_code == 404


# --- Issue #408 G1: CachedStaticFiles Cache-Control 회귀 가드 ---
# 정적 자원 응답에 장기 캐시 헤더가 포함되는지 확인
# Regression guard: static assets must include long-term Cache-Control header

def test_static_file_has_cache_control_immutable(client):
    """200 응답에 `public, max-age=31536000, immutable` Cache-Control 헤더가 포함된다.
    Verify CachedStaticFiles adds 1-year immutable Cache-Control on 200 responses.

    회귀 위험: src/main.py 의 CachedStaticFiles 가 StaticFiles 로 되돌아갈 때 차단.
    Regression guard: blocks downgrade from CachedStaticFiles back to plain StaticFiles.
    """
    response = client.get("/static/vendor/chart.umd.min.js")
    assert response.status_code == 200
    cc = response.headers.get("cache-control", "")
    assert "public" in cc, f"Cache-Control 에 'public' 없음: {cc!r}"
    assert "max-age=31536000" in cc, f"Cache-Control 에 'max-age=31536000' 없음: {cc!r}"
    assert "immutable" in cc, f"Cache-Control 에 'immutable' 없음: {cc!r}"


def test_static_404_no_cache_control_immutable(client):
    """404 응답에는 장기 캐시 헤더를 붙이지 않는다.
    Verify CachedStaticFiles does NOT add immutable Cache-Control on 404 responses."""
    response = client.get("/static/vendor/nonexistent.js")
    assert response.status_code == 404
    cc = response.headers.get("cache-control", "")
    assert "immutable" not in cc, f"404 응답에 immutable 헤더가 붙으면 안 됨: {cc!r}"


# --- S2: SESSION_SECRET 프로덕션 강제 (Phase B) ---

def test_lifespan_raises_when_default_session_secret_in_prod():
    """S2: prod 환경(https)에서 기본 SESSION_SECRET 사용 시 RuntimeError로 기동 차단.
    S2: Startup must raise RuntimeError when default SESSION_SECRET is used in production.
    """
    import pytest as _pytest  # pylint: disable=import-outside-toplevel
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "dev-secret-change-in-production"
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.app_base_url = "https://scamanager.example.com"
        mock_settings.token_encryption_key = "valid-key"
        mock_settings.strict_token_encryption = False
        mock_settings.telegram_webhook_secret = "some-secret"
        with _pytest.raises(RuntimeError, match="SESSION_SECRET must be changed in production"):
            with TestClient(app):
                pass


def test_lifespan_warns_default_session_secret_in_dev(caplog):
    """S2: dev 환경(http)에서는 기본 SESSION_SECRET 사용 시 경고만 출력 — 기동 허용.
    S2: Dev (http) environment should warn but not raise for default SESSION_SECRET.
    """
    import logging as _logging  # pylint: disable=import-outside-toplevel
    with patch("src.main._run_migrations"), \
         patch("src.main.settings") as mock_settings:
        mock_settings.session_secret = "dev-secret-change-in-production"
        mock_settings.anthropic_api_key = "sk-ant-test"
        mock_settings.app_base_url = "http://localhost:8000"
        mock_settings.token_encryption_key = ""
        mock_settings.strict_token_encryption = False
        mock_settings.telegram_webhook_secret = ""
        with caplog.at_level(_logging.WARNING, logger="src.main"):
            with TestClient(app):
                pass
    assert any("SESSION_SECRET" in rec.message for rec in caplog.records)


# --- S4: Content-Security-Policy 헤더 (Phase B) ---

def test_security_headers_include_csp(client):
    """S4: 모든 응답에 Content-Security-Policy 헤더가 포함되어야 한다.
    S4: All responses must include a Content-Security-Policy header.
    """
    response = client.get("/health")
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp, f"CSP default-src 'self' 없음: {csp!r}"
    assert "script-src" in csp, f"CSP script-src 없음: {csp!r}"
    assert "frame-ancestors 'none'" in csp, f"CSP frame-ancestors 없음: {csp!r}"


# --- LimitBodySizeMiddleware ValueError 회귀 가드 ---
# Content-Length 헤더가 숫자가 아닐 때 ValueError 가 발생하지 않고 400 을 반환해야 함
# Regression guard: LimitBodySizeMiddleware must handle non-numeric Content-Length gracefully

def test_limit_body_size_413_when_content_length_exceeds_10mb(client):
    """Content-Length 가 10MB + 1바이트(10485761)이면 413 Request Entity Too Large 반환.
    Returns 413 when Content-Length header exceeds the 10 MB limit by one byte.
    """
    # 10MB + 1 = 10485761 — _MAX_BODY(10485760) 초과
    # 10MB + 1 = 10485761 — exceeds _MAX_BODY (10 * 1024 * 1024)
    response = client.get("/health", headers={"Content-Length": "10485761"})
    assert response.status_code == 413, (
        f"10MB 초과 요청이 413 을 반환해야 하는데 {response.status_code} 반환"
    )


def test_limit_body_size_400_when_content_length_malformed(client):
    """Content-Length 헤더가 숫자로 변환 불가능한 값이면 400 Bad Request 반환.
    Returns 400 when Content-Length cannot be parsed as an integer (ValueError guard).

    회귀 위험: int(content_length) 직접 호출 시 ValueError 로 500 반환.
    Regression risk: calling int(content_length) without try/except raises ValueError → 500.
    """
    # "not-a-number" → int() 호출 시 ValueError 발생 — 400 으로 변환되어야 함
    # "not-a-number" → int() raises ValueError — must be caught and returned as 400
    response = client.get("/health", headers={"Content-Length": "not-a-number"})
    assert response.status_code == 400, (
        f"잘못된 Content-Length 가 400 을 반환해야 하는데 {response.status_code} 반환 "
        f"— ValueError 미처리 회귀 가드 실패"
    )


def test_limit_body_size_passes_normal_content_length(client):
    """Content-Length 가 정상 범위(1024바이트)이면 미들웨어를 통과하고 200 반환.
    Passes through LimitBodySizeMiddleware and returns 200 for a normal Content-Length value.
    """
    # 1024바이트 — _MAX_BODY(10485760) 미만이므로 통과
    # 1024 bytes — well within _MAX_BODY, middleware must pass through
    response = client.get("/health", headers={"Content-Length": "1024"})
    assert response.status_code == 200, (
        f"정상 Content-Length(1024) 요청이 200 을 반환해야 하는데 {response.status_code} 반환"
    )
