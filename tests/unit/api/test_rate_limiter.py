"""API Rate Limiting 테스트.
API rate limiting tests.
"""
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def test_rate_limiter_constants():
    """rate_limiter 모듈이 예상 상수를 export해야 한다.
    rate_limiter module must export expected constants.
    """
    from src.middleware.rate_limiter import limiter, RATE_LIMIT_API, RATE_LIMIT_HEAVY
    assert RATE_LIMIT_API == "60/minute"
    assert RATE_LIMIT_HEAVY == "10/minute"
    assert limiter is not None


def test_rate_limit_exceeded_returns_429():
    """제한 초과 시 429 Too Many Requests를 반환해야 한다.
    Must return 429 Too Many Requests when limit is exceeded.
    """
    test_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", config_filename="")
    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/limited")
    @test_limiter.limit("2/minute")
    async def _limited(request: Request):  # pylint: disable=unused-argument
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-Forwarded-For": "10.10.10.1"}  # NOSONAR python:S1313 — test-only private RFC-1918 address

    # 첫 두 번은 성공해야 함
    # First two calls must succeed
    assert client.get("/limited", headers=headers).status_code == 200
    assert client.get("/limited", headers=headers).status_code == 200
    # 세 번째는 429여야 함
    # Third call must return 429
    resp = client.get("/limited", headers=headers)
    assert resp.status_code == 429


def test_rate_limiter_uses_remote_address_key_func():
    """Limiter의 key_func이 get_remote_address여야 한다.
    Limiter must use get_remote_address as key_func.
    """
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel

    # get_remote_address는 slowapi 표준 IP 기반 키 함수
    # get_remote_address is the standard slowapi IP-based key function
    assert limiter._key_func is get_remote_address


def test_health_endpoint_no_rate_limit():
    """/health 엔드포인트는 rate limit 없이 반복 호출에도 200을 반환해야 한다.
    /health must always return 200 regardless of call frequency.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel

    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(15):
        r = client.get("/health")
    assert r.status_code == 200


def test_app_state_has_limiter():
    """app.state.limiter가 설정되어 있어야 한다.
    app.state.limiter must be configured.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel

    assert hasattr(app.state, "limiter")
    assert app.state.limiter is limiter
