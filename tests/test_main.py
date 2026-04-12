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
    # GET /health 응답 body 가 {"status": "ok"} 인지 검증
    response = client.get("/health")
    assert response.json() == {"status": "ok"}


# --- 라우트 등록 검증 ---

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
