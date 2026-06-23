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
# Claude 모델 기본값 명시 — .env.example 이 빈값으로 설정되어 Python default 를 override 하는 버그 방지
# Explicitly set Claude model defaults — .env.example sets empty values that would override Python defaults
os.environ["CLAUDE_REVIEW_MODEL"] = "claude-sonnet-4-6"
os.environ["CLAUDE_INSIGHT_MODEL"] = "claude-haiku-4-5"
# 테스트 환경 = 개발 모드 명시 opt-out — API_KEY 미설정 시 REST API fail-closed(503) 기본값을
# 우회해 기존 endpoint 테스트(repos/stats 등 키 없이 200 의존)를 보존한다. fail-closed 기본값
# 자체는 tests/unit/api/test_auth.py 가 api_auth_disabled=False 로 직접 검증.
# Test env = explicit dev opt-out — bypass the fail-closed(503) default for unset API_KEY so existing
# endpoint tests (repos/stats relying on keyless 200) keep passing. The fail-closed default itself is
# verified directly by test_auth.py with api_auth_disabled=False.
os.environ["API_AUTH_DISABLED"] = "1"

from src.main import app
from src.ui.routes import add_repo as _add_repo_module
from src.webhook import router as webhook_router


@pytest.fixture(autouse=True)
def _clear_webhook_secret_cache():
    webhook_router._webhook_secret_cache.clear()
    yield
    webhook_router._webhook_secret_cache.clear()


@pytest.fixture(autouse=True)
def _clear_user_repos_cache():
    # GitHub 리포 TTL 캐시 — 테스트 간 격리 보장
    # Clear GitHub repos TTL cache to ensure test isolation.
    _add_repo_module._user_repos_cache.clear()
    yield
    _add_repo_module._user_repos_cache.clear()


@pytest.fixture(autouse=True)
def _clear_otp_attempt_limiter():
    # Telegram OTP brute-force 슬라이딩 윈도우 (C12) — 모듈 레벨 싱글톤, 테스트 간 격리
    # Telegram OTP brute-force sliding window (C12) — module-level singleton, isolate per test
    from src.notifier.telegram_commands import _otp_limiter  # pylint: disable=import-outside-toplevel
    _otp_limiter._failures.clear()
    yield
    _otp_limiter._failures.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Rate limiter 인메모리 카운터를 테스트마다 초기화한다 — 테스트 간 rate limit 누적 방지.
    Reset in-memory rate limiter counters between tests to prevent cross-test leakage.
    """
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel
    yield
    try:
        limiter._storage.reset()  # limits.MemoryStorage.reset() — 모든 카운터 초기화
    except Exception:  # pylint: disable=broad-except
        pass


@pytest.fixture
def client():
    return TestClient(app)
