"""retry-pending-merges cron 엔드포인트 단위 테스트 (Phase 12 T10).
Unit tests for the retry-pending-merges internal cron endpoint (Phase 12 T10).
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

# 라우터만 붙인 독립 테스트 앱 — main.py 등록 없이 단위 테스트용
# Standalone test app with only the cron router — for unit testing without main.py
_app = FastAPI()
_app.include_router(router)

client = TestClient(_app, raise_server_exceptions=True)

_VALID_KEY = "test-cron-key-for-unit-tests"
_WRONG_KEY = "wrong-key"


def test_retry_endpoint_no_key_returns_401(monkeypatch):
    """X-API-Key 헤더 없이 /retry-pending-merges 요청 시 401을 반환한다.
    Returns 401 when X-API-Key header is absent.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    resp = client.post("/api/internal/cron/retry-pending-merges")
    assert resp.status_code == 401


def test_retry_endpoint_unconfigured_key_returns_503(monkeypatch):
    """INTERNAL_CRON_API_KEY 미설정 시 503을 반환한다.
    Returns 503 when INTERNAL_CRON_API_KEY is not configured.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", "")
    resp = client.post(
        "/api/internal/cron/retry-pending-merges",
        headers={"X-API-Key": _VALID_KEY},
    )
    assert resp.status_code == 503


def test_retry_endpoint_returns_counts(monkeypatch):
    """올바른 키로 /retry-pending-merges 요청 시 counts 딕셔너리를 반환한다.
    Returns counts dict when called with valid key.
    """
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _VALID_KEY)
    monkeypatch.setattr("src.config.settings.merge_retry_worker_batch_size", 50)
    mock_counts = {
        "claimed": 2,
        "succeeded": 1,
        "terminal": 0,
        "abandoned": 0,
        "released": 1,
        "skipped": 0,
    }
    with patch(
        "src.api.internal_cron.process_pending_retries",
        new_callable=AsyncMock,
        return_value=mock_counts,
    ):
        resp = client.post(
            "/api/internal/cron/retry-pending-merges",
            headers={"X-API-Key": _VALID_KEY},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["counts"] == mock_counts
