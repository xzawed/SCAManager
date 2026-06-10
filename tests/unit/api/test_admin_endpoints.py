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
from src.api.admin import _get_worker_db as _api_get_worker_db  # noqa: F401  pylint: disable=unused-import
from src.auth.session import CurrentUser, require_admin
from src.database import Base
from src.main import app
from src.ui.routes.admin import _get_db as _ui_get_db  # noqa: F401  pylint: disable=unused-import
from src.ui.routes.admin import _get_worker_db as _ui_get_worker_db  # noqa: F401  pylint: disable=unused-import


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
    # tenants/operations 는 worker 세션 의존성(_get_worker_db)을 쓰므로 동일 db_session 으로 override.
    # rls-audit 는 _get_db(웹) 유지 — 두 의존성 모두 동일 in-memory 세션을 가리킨다.
    # tenants/operations use the worker-session dependency → override to the same db_session;
    # rls-audit keeps _get_db (web). Both dependencies point to the same in-memory session.
    app.dependency_overrides[_api_get_worker_db] = lambda: db_session
    app.dependency_overrides[_ui_get_worker_db] = lambda: db_session
    yield TestClient(app)
    # 본인 override 만 제거 (다른 테스트 override 보존)
    app.dependency_overrides.pop(require_admin, None)
    app.dependency_overrides.pop(_api_get_db, None)
    app.dependency_overrides.pop(_ui_get_db, None)
    app.dependency_overrides.pop(_api_get_worker_db, None)
    app.dependency_overrides.pop(_ui_get_worker_db, None)


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
    assert data["summary"]["total"] == 11
    assert data["summary"]["applied"] == 11


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


# ─── RLS Phase 3 — rls_coverage_summary db 전달 가드 ──────────────────
# ─── RLS Phase 3 — rls_coverage_summary db-forwarding guards ─────────


# mock summary — force_applied 실측 도입 후에도 직렬화/렌더링 호환 형태
# Mock summary — serialization/render-compatible shape after the force live-check lands
_SUMMARY_STUB = {"total": 11, "applied": 11, "missing": 0, "force_applied": False}


def _passed_arguments(mock_call) -> list:
    """mock 호출의 positional + keyword 인자값을 단일 리스트로 평탄화.

    Flattens positional + keyword argument values of a mock call into one list.
    """
    return list(mock_call.args) + list(mock_call.kwargs.values())


def test_get_rls_audit_passes_db_to_coverage_summary(client):
    """GET /api/admin/rls-audit — rls_coverage_summary 에 non-None db 전달 (RLS Phase 3).

    GET /api/admin/rls-audit must forward a non-None db session into
    rls_coverage_summary so force_applied reflects live pg_class state.
    """
    from unittest.mock import patch

    with patch(
        "src.api.admin.saas_service.rls_coverage_summary", return_value=_SUMMARY_STUB
    ) as mock_summary:
        response = client.get("/api/admin/rls-audit")
    assert response.status_code == 200
    mock_summary.assert_called_once()
    passed = _passed_arguments(mock_summary.call_args)
    # db 인자 (positional 또는 keyword) 가 non-None 으로 전달돼야 한다
    # The db argument (positional or keyword) must be forwarded as non-None
    assert passed, "rls_coverage_summary 가 db 인자 없이 호출됨 / called without a db argument"
    assert passed[0] is not None, "db 인자가 None — 실측 경로 비활성 / db is None, live check disabled"


def test_admin_rls_audit_html_passes_db_to_coverage_summary(client):
    """GET /admin/rls-audit (UI) — rls_coverage_summary 에 non-None db 전달 (RLS Phase 3).

    The UI route GET /admin/rls-audit must forward a non-None db session into
    rls_coverage_summary — same contract as the REST endpoint.
    """
    from unittest.mock import patch

    with patch(
        "src.ui.routes.admin.saas_service.rls_coverage_summary",
        return_value=_SUMMARY_STUB,
    ) as mock_summary:
        response = client.get("/admin/rls-audit")
    assert response.status_code == 200
    mock_summary.assert_called_once()
    passed = _passed_arguments(mock_summary.call_args)
    assert passed, "rls_coverage_summary 가 db 인자 없이 호출됨 / called without a db argument"
    assert passed[0] is not None, "db 인자가 None — 실측 경로 비활성 / db is None, live check disabled"


# ─── RLS Phase 4 — 엔드포인트별 세션 라우팅 계약 가드 ──────────────────────
# cross-tenant(tenants/operations)=worker 세션 / 진단(rls-audit)=웹 세션. distinct sentinel 로
# 의존성 wiring 을 봉인 — 정적 import 가드(test_worker_session_routing)가 못 잡는 endpoint swap 차단.
# Per-endpoint session-routing contract: cross-tenant aggregates use the worker session, the
# diagnostic uses the web session. Distinct sentinels lock the wiring against an accidental swap.

@pytest.fixture
def _sentinel_client(admin_user, db_session):
    """worker dep 과 web dep 을 **구별되는** 세션으로 override 한 client.
    Overrides the worker dep and the web dep with DISTINGUISHABLE sessions."""
    worker_session = db_session  # 실DB(in-memory) — tenants/operations 가 실제 쿼리 가능
    web_marker = object()        # rls-audit 가 받는 세션 식별용 sentinel (쿼리 안 함 — 전부 mock)
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[_api_get_worker_db] = lambda: worker_session
    app.dependency_overrides[_ui_get_worker_db] = lambda: worker_session
    app.dependency_overrides[_api_get_db] = lambda: web_marker
    app.dependency_overrides[_ui_get_db] = lambda: web_marker
    yield TestClient(app), worker_session, web_marker
    for dep in (require_admin, _api_get_worker_db, _ui_get_worker_db, _api_get_db, _ui_get_db):
        app.dependency_overrides.pop(dep, None)


def test_tenants_uses_worker_session_not_web(_sentinel_client):
    """/api/admin/tenants 의 tenant_inventory 는 worker 세션을 받아야 한다 (web sentinel 아님)."""
    from unittest.mock import patch
    client, worker_session, web_marker = _sentinel_client
    with patch("src.api.admin.saas_service.tenant_inventory", return_value=[]) as mock_inv:
        assert client.get("/api/admin/tenants").status_code == 200
    db_arg = _passed_arguments(mock_inv.call_args)[0]
    assert db_arg is worker_session, "tenants 가 worker 세션이 아닌 web 세션 사용 — Phase 4 under-report 회귀"
    assert db_arg is not web_marker


def test_operations_uses_worker_session_not_web(_sentinel_client):
    """/api/admin/operations 의 operations_kpi 는 worker 세션을 받아야 한다."""
    from unittest.mock import patch
    client, worker_session, web_marker = _sentinel_client
    with patch("src.api.admin.operations_service.operations_kpi", return_value={}) as mock_kpi:
        assert client.get("/api/admin/operations").status_code == 200
    db_arg = _passed_arguments(mock_kpi.call_args)[0]
    assert db_arg is worker_session, "operations 가 worker 세션이 아닌 web 세션 사용 — Phase 4 under-report 회귀"


def test_rls_audit_uses_web_session_not_worker(_sentinel_client):
    """/api/admin/rls-audit 의 rls_coverage_summary 는 **웹** 세션을 받아야 한다.

    rls-audit 진단(connection_bypasses_rls)은 웹 app role connection 으로 평가돼야 정확 —
    worker(BYPASSRLS) 세션이면 항상 우회=TRUE 오진단.
    """
    from unittest.mock import patch
    client, worker_session, web_marker = _sentinel_client
    with patch(
        "src.api.admin.saas_service.rls_coverage_summary", return_value=_SUMMARY_STUB
    ) as mock_summary:
        assert client.get("/api/admin/rls-audit").status_code == 200
    db_arg = _passed_arguments(mock_summary.call_args)[0]
    assert db_arg is web_marker, "rls-audit 가 web 세션이 아닌 worker 세션 사용 — BYPASSRLS 오진단 회귀"
    assert db_arg is not worker_session


def test_api_get_worker_db_yields_and_closes():
    """api/admin._get_worker_db 제너레이터가 WorkerSessionLocal 세션을 yield 후 close 한다.

    엔드포인트 경로는 의존성 override 로 본문이 실행되지 않으므로 제너레이터를 직접 호출해
    커버 (test_failover::TestGetDb 패턴 미러).
    """
    from unittest.mock import MagicMock, patch
    from src.api import admin as admin_mod
    mock_session = MagicMock()
    with patch.object(admin_mod, "WorkerSessionLocal", return_value=mock_session):
        gen = admin_mod._get_worker_db()
        assert next(gen) is mock_session
        # 제너레이터 소진 → finally → close
        try:
            next(gen)
        except StopIteration:
            pass
    mock_session.close.assert_called_once()


def test_ui_get_worker_db_yields_and_closes():
    """ui/routes/admin._get_worker_db 제너레이터도 동일 계약 (yield + close)."""
    from unittest.mock import MagicMock, patch
    from src.ui.routes import admin as ui_admin_mod
    mock_session = MagicMock()
    with patch.object(ui_admin_mod, "WorkerSessionLocal", return_value=mock_session):
        gen = ui_admin_mod._get_worker_db()
        assert next(gen) is mock_session
        try:
            next(gen)
        except StopIteration:
            pass
    mock_session.close.assert_called_once()


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


# ─── Cycle 120 — OPERATIONS_DASHBOARD_DISABLED kill-switch 회귀 가드 ────────


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
