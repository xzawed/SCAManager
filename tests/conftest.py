import os
import pytest
from fastapi.testclient import TestClient

# 사이클 65 fix — pre-existing 5 fail (사이클 62~64 누적 보류) 정밀 조사 결과:
# `.env` 가 셸 환경에 export 된 환경 (예: direnv, 또는 사용자 셸 config) 에서는
# `os.environ.setdefault` 가 무시되어 운영 토큰 (TELEGRAM_BOT_TOKEN 등) 이 settings 로 들어감.
# 단위 테스트의 하드코딩 HMAC 토큰 ("123:ABC" 기반) 과 mismatch → 5 fail.
# 직접 set 으로 변경 — 모든 환경에서 일관 (CI 도 동일 값 명시 — `.github/workflows/ci.yml` L51).
# Fix for cycle 65: replaced setdefault with direct assignment so test env vars always win
# over .env exports — prevents 5 pre-existing flaky fails caused by HMAC token mismatch.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GITHUB_WEBHOOK_SECRET"] = "test_secret"
os.environ["GITHUB_TOKEN"] = "ghp_test"
os.environ["TELEGRAM_BOT_TOKEN"] = "123:ABC"
os.environ["TELEGRAM_CHAT_ID"] = "-100123"
os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"
os.environ["GITHUB_CLIENT_ID"] = "test-github-client-id"
os.environ["GITHUB_CLIENT_SECRET"] = "test-github-client-secret"
os.environ["SESSION_SECRET"] = "test-session-secret-32-chars-long!"

from src.main import app
from src.webhook import router as webhook_router


@pytest.fixture(autouse=True)
def _clear_webhook_secret_cache():
    webhook_router._webhook_secret_cache.clear()
    yield
    webhook_router._webhook_secret_cache.clear()


@pytest.fixture
def client():
    return TestClient(app)
