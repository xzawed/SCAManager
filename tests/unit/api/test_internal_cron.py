"""내부 Cron 엔드포인트 단위 테스트.
Unit tests for the internal cron API endpoints.
"""
import os

# src 임포트 전 환경변수 주입 필수
# Environment variables must be injected before any src.* imports
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import AsyncMock, patch  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.api.internal_cron import router  # noqa: E402

# 라우터만 붙인 독립 테스트 앱 — main.py 등록 전(T10 이전) 단위 테스트용
# Standalone test app with only the cron router — for unit testing before main.py wires it (T10)
_app = FastAPI()
_app.include_router(router)

client = TestClient(_app, raise_server_exceptions=True)

_VALID_KEY = "test-cron-key-for-unit-tests"
_WRONG_KEY = "wrong-key"


# ---------------------------------------------------------------------------
# 인증 실패 케이스
# Authentication failure cases
# ---------------------------------------------------------------------------


def test_weekly_endpoint_requires_api_key(monkeypatch):
    """X-API-Key 헤더 없이 /weekly 요청 시 401을 반환한다.
    Returns 401 when X-API-Key header is absent on /weekly.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    resp = client.post("/api/internal/cron/weekly")
    assert resp.status_code == 401


def test_weekly_endpoint_with_wrong_key_returns_401(monkeypatch):
    """잘못된 X-API-Key로 /weekly 요청 시 401을 반환한다.
    Returns 401 when X-API-Key header contains an incorrect key on /weekly.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    resp = client.post(
        "/api/internal/cron/weekly",
        headers={"X-API-Key": _WRONG_KEY},
    )
    assert resp.status_code == 401


def test_trend_endpoint_requires_api_key(monkeypatch):
    """X-API-Key 헤더 없이 /trend 요청 시 401을 반환한다.
    Returns 401 when X-API-Key header is absent on /trend.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    resp = client.post("/api/internal/cron/trend")
    assert resp.status_code == 401


def test_trend_endpoint_with_wrong_key_returns_401(monkeypatch):
    """잘못된 X-API-Key로 /trend 요청 시 401을 반환한다.
    Returns 401 when X-API-Key header contains an incorrect key on /trend.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    resp = client.post(
        "/api/internal/cron/trend",
        headers={"X-API-Key": _WRONG_KEY},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 키 미설정 케이스 (503)
# Key not configured case (503)
# ---------------------------------------------------------------------------


def test_weekly_endpoint_returns_503_when_key_not_configured(monkeypatch):
    """`internal_cron_api_key` 미설정 시 503을 반환한다.
    Returns 503 when internal_cron_api_key is not configured.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", "")
    resp = client.post(
        "/api/internal/cron/weekly",
        headers={"X-API-Key": _VALID_KEY},
    )
    assert resp.status_code == 503


def test_trend_endpoint_returns_503_when_key_not_configured(monkeypatch):
    """`internal_cron_api_key` 미설정 시 503을 반환한다.
    Returns 503 when internal_cron_api_key is not configured on /trend.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", "")
    resp = client.post(
        "/api/internal/cron/trend",
        headers={"X-API-Key": _VALID_KEY},
    )
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# 정상 동작 케이스
# Success cases
# ---------------------------------------------------------------------------


def test_weekly_endpoint_invokes_run_weekly_reports(monkeypatch):
    """올바른 키로 /weekly 요청 시 200과 {"status":"ok","sent":N} 응답을 반환한다.
    Returns 200 with {"status":"ok","sent":N} when the correct key is provided on /weekly.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    with patch(
        "src.api.internal_cron.run_weekly_reports",
        new_callable=AsyncMock,
        return_value=3,
    ) as mock_fn:
        resp = client.post(
            "/api/internal/cron/weekly",
            headers={"X-API-Key": _VALID_KEY},
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "sent": 3}
    # run_weekly_reports가 정확히 한 번 호출되었는지 확인
    # Verify run_weekly_reports was awaited exactly once
    mock_fn.assert_awaited_once()


def test_trend_endpoint_invokes_run_trend_check(monkeypatch):
    """올바른 키로 /trend 요청 시 200과 {"status":"ok","alerted":N} 응답을 반환한다.
    Returns 200 with {"status":"ok","alerted":N} when the correct key is provided on /trend.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    with patch(
        "src.api.internal_cron.run_trend_check",
        new_callable=AsyncMock,
        return_value=2,
    ) as mock_fn:
        resp = client.post(
            "/api/internal/cron/trend",
            headers={"X-API-Key": _VALID_KEY},
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "alerted": 2}
    # run_trend_check가 정확히 한 번 호출되었는지 확인
    # Verify run_trend_check was awaited exactly once
    mock_fn.assert_awaited_once()


def test_weekly_endpoint_returns_zero_when_no_repos(monkeypatch):
    """리포가 없어 sent=0인 경우에도 200을 반환한다.
    Returns 200 with sent=0 when there are no repositories to report on.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    with patch(
        "src.api.internal_cron.run_weekly_reports",
        new_callable=AsyncMock,
        return_value=0,
    ):
        resp = client.post(
            "/api/internal/cron/weekly",
            headers={"X-API-Key": _VALID_KEY},
        )
    assert resp.status_code == 200
    assert resp.json()["sent"] == 0


def test_trend_endpoint_returns_zero_when_no_alerts(monkeypatch):
    """트렌드 하락 없어 alerted=0인 경우에도 200을 반환한다.
    Returns 200 with alerted=0 when no trend alerts are needed.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    with patch(
        "src.api.internal_cron.run_trend_check",
        new_callable=AsyncMock,
        return_value=0,
    ):
        resp = client.post(
            "/api/internal/cron/trend",
            headers={"X-API-Key": _VALID_KEY},
        )
    assert resp.status_code == 200
    assert resp.json()["alerted"] == 0
