"""Cycle 79 PR 3a — admin REST API + UI 라우트 회귀 가드.

require_admin Depends 위임 — 3-layer 검증 (kill-switch / login / allow-list).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# 모든 ORM 모델 import — Base.metadata 에 테이블 정의 보장 (in-memory create_all 페어)
# Import all ORM models — guarantee Base.metadata table definitions for in-memory create_all
import src.models  # noqa: F401  pylint: disable=unused-import  # side-effect import
from src.api.admin import _get_db as _api_get_db  # noqa: F401  pylint: disable=unused-import
from src.auth.session import CurrentUser, require_admin
from src.database import Base
from src.main import app
from src.ui.routes.admin import _get_db as _ui_get_db  # noqa: F401  pylint: disable=unused-import


@pytest.fixture
def admin_user():
    return CurrentUser(
        id=1,
        github_login="admin",
        email="admin@example.com",
        display_name="Admin",
        plaintext_token="ghp_admin",
    )


@pytest.fixture
def db_session():
    """단위 테스트용 in-memory SQLite session (StaticPool — connection sharing)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    # StaticPool = single-connection sharing (in-memory SQLite 의 핵심 패턴)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(admin_user, db_session):
    """admin override + DB session override — require_admin 통과 + DB sharing.

    본인 override 만 setup/teardown — 다른 테스트의 override 영향 X.
    """
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[_api_get_db] = lambda: db_session
    app.dependency_overrides[_ui_get_db] = lambda: db_session
    yield TestClient(app)
    # 본인 override 만 제거 (다른 테스트 override 보존)
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(_api_get_db, None)
    app.dependency_overrides.pop(_ui_get_db, None)


def test_get_tenants_returns_inventory(client):
    """GET /api/admin/tenants — total_tenants + tenants list 반환."""
    response = client.get("/api/admin/tenants")
    assert response.status_code == 200
    data = response.json()
    assert "total_tenants" in data
    assert "tenants" in data
    assert isinstance(data["tenants"], list)


def test_get_rls_audit_returns_matrix(client):
    """GET /api/admin/rls-audit — summary + matrix 반환."""
    response = client.get("/api/admin/rls-audit")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "matrix" in data
    assert data["summary"]["total"] == 10
    assert data["summary"]["applied"] == 10


def test_admin_tenants_html_renders(client):
    """GET /admin/tenants — HTML 렌더링.

    Phase 2 PR-8 (사이클 84) — i18n 적용 후 default locale 'en' 또는 'ko' 양호.
    Phase 2 PR-8 (Cycle 84) — after i18n, accept either default locale en or ko.
    """
    response = client.get("/admin/tenants")
    assert response.status_code == 200
    assert "Tenant Inventory" in response.text or "Tenant 인벤토리" in response.text
    assert "Total tenants" in response.text or "총 테넌트" in response.text


def test_admin_rls_audit_html_renders(client):
    """GET /admin/rls-audit — HTML 렌더링 + 매트릭스 표시."""
    response = client.get("/admin/rls-audit")
    assert response.status_code == 200
    assert "RLS Policy Audit" in response.text
    # 5 새 테이블 모두 표시 확인
    assert "users" in response.text
    assert "repo_configs" in response.text
    assert "gate_decisions" in response.text
    assert "merge_retry_queue" in response.text
    assert "analysis_feedbacks" in response.text


def test_admin_endpoints_blocked_when_kill_switch(monkeypatch):
    """kill-switch 활성 시 admin endpoint 모두 503 — require_admin Layer 1 통합 검증."""
    # require_admin override 제거 — 실제 require_admin 동작 검증
    app.dependency_overrides.pop(require_admin, None)
    monkeypatch.setenv("SAAS_MULTITENANT_DISABLED", "1")
    c = TestClient(app)
    response = c.get("/api/admin/tenants")
    assert response.status_code == 503
    response = c.get("/admin/tenants")
    assert response.status_code == 503


# ─── Cycle 80 PR 2 — operations endpoint 회귀 가드 ────────────────────


def test_get_operations_returns_kpi(client):
    """GET /api/admin/operations — KPI 5종 반환."""
    response = client.get("/api/admin/operations")
    assert response.status_code == 200
    data = response.json()
    assert "cache" in data
    assert "api_cost" in data
    assert "merge" in data
    assert "pipeline_latency" in data


def test_admin_operations_html_renders(client):
    """GET /admin/operations — HTML 렌더링."""
    response = client.get("/admin/operations")
    assert response.status_code == 200
    assert "Operations" in response.text or "운영 모니터링" in response.text


def test_admin_operations_blocked_when_kill_switch(monkeypatch):
    """GET /admin/operations — kill-switch 활성 시 503."""
    app.dependency_overrides.pop(require_admin, None)
    monkeypatch.setenv("SAAS_MULTITENANT_DISABLED", "1")
    c = TestClient(app)
    response = c.get("/admin/operations")
    assert response.status_code == 503
    response = c.get("/api/admin/operations")
    assert response.status_code == 503


# ─── Cycle 111 — OPERATIONS_DASHBOARD_DISABLED kill-switch 회귀 가드 ────────


def test_admin_operations_kill_switch_returns_503(client):
    """OPERATIONS_DASHBOARD_DISABLED=1 시 /admin/operations 가 503 을 반환한다.

    When OPERATIONS_DASHBOARD is disabled via kill-switch, /admin/operations returns 503.
    """
    from unittest.mock import patch

    with patch("src.ui.routes.admin.is_disabled", return_value=True):
        response = client.get("/admin/operations")
    assert response.status_code == 503


def test_admin_operations_active_returns_200(client):
    """kill-switch 비활성 시 /admin/operations 가 200 을 반환한다.

    When kill-switch is inactive, /admin/operations returns 200 with KPI context.
    """
    from unittest.mock import MagicMock, patch

    # MagicMock — 템플릿이 중첩 속성 접근(kpi.cache.hit_rate 등)을 자동 처리
    # MagicMock — handles nested attribute access (kpi.cache.hit_rate etc.) automatically
    with patch("src.ui.routes.admin.is_disabled", return_value=False), patch(
        "src.ui.routes.admin.operations_service.operations_kpi",
        return_value=MagicMock(),
    ):
        response = client.get("/admin/operations")
    assert response.status_code == 200
