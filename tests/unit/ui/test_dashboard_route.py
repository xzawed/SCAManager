"""GET /dashboard UI 라우트 단위 테스트 — Phase 1 PR 4 (MVP-B 신규 라우트).

검증:
- 인증 (require_login) — 미로그인 302 redirect
- 로그인 + mock service → 200 + KPI/trend/frequent_issues context
- days 쿼리 파라미터가 service 함수에 전달
- 템플릿 렌더링 (TemplateResponse mock)
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.auth.session import CurrentUser, require_login
from src.main import app


_TEST_USER = CurrentUser(
    id=1,
    github_login="tester",
    email="t@x.com",
    display_name="Tester",
    plaintext_token="",
)


@contextmanager
def _ctx(db):
    yield db


@pytest.fixture(autouse=True)
def _override_login():
    """모든 테스트에서 require_login override → _TEST_USER 주입."""
    _prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _TEST_USER
    yield
    if _prev is not None:
        app.dependency_overrides[require_login] = _prev
    else:
        app.dependency_overrides.pop(require_login, None)


# ─── 인증 ──────────────────────────────────────────────────────────────────


def test_dashboard_requires_login():
    """미로그인 시 require_login 의 redirect 또는 401 응답.

    autouse fixture 를 일시 제거하여 인증 거부 흐름 검증.
    """
    app.dependency_overrides.pop(require_login, None)
    try:
        client = TestClient(app, follow_redirects=False)
        response = client.get("/dashboard")
        # require_login 패턴: 302 (login redirect) 또는 401
        assert response.status_code in (302, 401, 303), (
            f"미로그인 시 302/401 기대, 실제: {response.status_code}"
        )
    finally:
        app.dependency_overrides[require_login] = lambda: _TEST_USER


# ─── 200 OK + service 호출 ─────────────────────────────────────────────────


def test_dashboard_returns_200():
    """로그인 + service mock → GET /dashboard 200 응답."""
    client = TestClient(app)

    fake_kpi = {
        "avg_score": {"value": 82.3, "grade": "B", "delta": 3.1},
        "analysis_count": {"value": 42, "delta": 4},
        "high_security_issues": {"value": 3, "delta": -2},
        "active_repos": {"value": 12, "total": 15, "delta": 0},
    }
    fake_trend = [{"date": "2026-04-30", "avg_score": 82.0, "count": 5}]
    fake_issues = [{"message": "X", "count": 3, "category": "code_quality", "language": "python", "tool": "pylint"}]

    mock_db = MagicMock()
    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value=fake_kpi), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=fake_trend), \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=fake_issues), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse") as mock_tr:
        from fastapi.responses import HTMLResponse
        mock_tr.return_value = HTMLResponse(content="<html>dashboard</html>", status_code=200)
        response = client.get("/dashboard")

    assert response.status_code == 200


def test_dashboard_default_days_is_7():
    """days 쿼리 파라미터 미지정 시 기본값 7 적용."""
    client = TestClient(app)
    mock_db = MagicMock()

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value={}) as mock_kpi, \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[]), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse") as mock_tr:
        from fastapi.responses import HTMLResponse
        mock_tr.return_value = HTMLResponse(content="<html>x</html>", status_code=200)
        client.get("/dashboard")

    assert mock_kpi.called
    args, kwargs = mock_kpi.call_args
    days = kwargs.get("days") if "days" in kwargs else (args[1] if len(args) > 1 else None)
    assert days == 7


def test_dashboard_respects_days_param():
    """?days=30 쿼리 파라미터가 service 호출 시 days=30 으로 전달."""
    client = TestClient(app)
    mock_db = MagicMock()

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value={}) as mock_kpi, \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=[]) as mock_trend, \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[]), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse") as mock_tr:
        from fastapi.responses import HTMLResponse
        mock_tr.return_value = HTMLResponse(content="<html>x</html>", status_code=200)
        client.get("/dashboard?days=30")

    for mock in (mock_kpi, mock_trend):
        args, kwargs = mock.call_args
        days_val = kwargs.get("days") if "days" in kwargs else (args[1] if len(args) > 1 else None)
        assert days_val == 30, f"{mock} days=30 미전달 (실제: {days_val})"


def test_dashboard_context_includes_kpi_trend_issues():
    """템플릿 컨텍스트에 kpi/trend/frequent_issues/days 키 포함."""
    client = TestClient(app)
    mock_db = MagicMock()
    captured: dict = {}

    def _capture(request, template_name, context, **kwargs):
        captured.update(context)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>x</html>", status_code=200)

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value={"avg_score": {"value": 80}}), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value={"value": 16.6}), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[{"reason": "unstable_ci", "count": 5, "share_pct": 79.0}]), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard")

    assert response.status_code == 200
    # Phase 1 + Phase 2 PR 1 신규 키
    for key in ("kpi", "trend", "frequent_issues", "days", "current_user",
                "auto_merge", "merge_failures"):
        assert key in captured, f"context 에 {key} 누락"
