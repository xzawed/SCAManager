"""scan-security cron 엔드포인트 단위 테스트 (Cycle 73 F1 — CI fix-up)."""
import os

# src 임포트 전 환경변수 주입 필수
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

_app = FastAPI()
_app.include_router(router)
client = TestClient(_app, raise_server_exceptions=True)

_VALID_KEY = "test-cron-key-for-unit-tests"


def test_security_scan_endpoint_no_key_returns_401(monkeypatch):
    """X-API-Key 헤더 없이 /scan-security 요청 시 401."""
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    resp = client.post("/api/internal/cron/scan-security")
    assert resp.status_code == 401


def test_security_scan_endpoint_with_key_invokes_service(monkeypatch):
    """유효 키 시 service 호출 + 200 + totals 반환."""
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    fake_totals = {"code_scanning": 3, "secret_scanning": 0, "skipped": 0, "repos": 1}
    with patch(
        "src.api.internal_cron.scan_all_repos",
        new=AsyncMock(return_value=fake_totals),
    ):
        resp = client.post(
            "/api/internal/cron/scan-security",
            headers={"X-API-Key": _VALID_KEY},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["totals"] == fake_totals
