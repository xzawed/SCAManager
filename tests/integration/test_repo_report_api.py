"""Repo Report API 통합 테스트 — 실제 DB 사용.
Integration tests for repo report API using real database.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from src.database import Base, FailoverSessionFactory
from src.main import app

# ORM 모델 import — Base.metadata 등록 의무 (lazy import 금지)
# ORM model imports register tables on Base.metadata (no lazy imports allowed)
from src.models.repository import Repository  # noqa: F401
from src.models.analysis import Analysis  # noqa: F401

client = TestClient(app)


@pytest.fixture()
def report_db():
    """테이블 생성된 in-memory SQLite 를 /api/repo_report 라우터에 주입.

    Provides an in-memory SQLite DB with schema for repo_report router tests.
    StaticPool 로 세션 간 동일 커넥션 공유 — 테이블 가시성 보장.
    StaticPool shares the same connection across sessions — tables are visible.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = FailoverSessionFactory(engine)
    with patch("src.api.repo_report.SessionLocal", factory):
        yield factory


@pytest.mark.slow
def test_list_repos_report_auth_required():
    """API 키 설정 후 헤더 미제공 → 401.
    API key configured but header omitted → 401.
    """
    # settings.api_key 를 직접 mock — monkeypatch.setenv 는 singleton 초기화 이후 무효
    # Mock settings.api_key directly — monkeypatch.setenv is ineffective after singleton init
    with patch("src.api.auth.settings") as mock_settings:
        mock_settings.api_key = "integration-key"
        mock_settings.app_base_url = "http://localhost"
        resp = client.get("/api/repos/report")
    assert resp.status_code == 401


@pytest.mark.slow
def test_list_repos_report_returns_json(report_db):
    """인증 성공 시 JSON 응답 반환 (빈 DB).
    Returns JSON response for empty DB in dev mode.
    """
    # API_KEY 미설정 개발 모드에서는 인증 없이 통과 (conftest.py 에 API_KEY 미설정)
    # In dev mode (no API_KEY in conftest), requests pass without auth
    resp = client.get("/api/repos/report")
    assert resp.status_code == 200
    data = resp.json()
    assert "repos" in data
    assert "summary" in data
    assert "generated_at" in data


@pytest.mark.slow
def test_get_repo_report_not_found(report_db):
    """존재하지 않는 repo → 404.
    Non-existent repo → 404.
    """
    # API_KEY 미설정 개발 모드 — 인증 통과, DB 조회 결과 없음 → 404
    # Dev mode (no API_KEY) — auth passes, DB returns None → 404
    resp = client.get("/api/repos/nonexistent/repo/report")
    assert resp.status_code == 404
