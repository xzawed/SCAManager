"""GET /dashboard UI 라우트 단위 테스트 — Phase 1 PR 4 (MVP-B 신규 라우트).
GET /dashboard UI route unit tests — Phase 1 PR 4 (MVP-B new route).

검증:
- 인증 (require_login) — 미로그인 302 redirect
- 로그인 + mock service → 200 + KPI/trend/frequent_issues context
- days 쿼리 파라미터가 service 함수에 전달
- 템플릿 렌더링 (TemplateResponse mock)

Phase 3 PR 3 (2026-05-03) 추가 — `mode=overview|insight` 분기 검증:
Phase 3 PR 3 (2026-05-03) added — `mode=overview|insight` branch verification:
- default mode = overview (기존 동작 보존)
- mode=insight → dashboard_service.insight_narrative (async) 호출 + insight 컨텍스트 주입
- whitelist 외 값 → overview 로 fallback
- 모드 토글 UI 링크 2건 (overview / insight) 존재
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

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
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": False, "count": 0, "recent_analysis": None}), \
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
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": False, "count": 0, "recent_analysis": None}), \
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
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": False, "count": 0, "recent_analysis": None}), \
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
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": True, "count": 0, "recent_analysis": None}), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard")

    assert response.status_code == 200
    # Phase 1 + Phase 2 PR 1 신규 키
    for key in ("kpi", "trend", "frequent_issues", "days", "current_user",
                "auto_merge", "merge_failures", "feedback"):
        assert key in captured, f"context 에 {key} 누락"


# ─── Phase 3 PR 3 (2026-05-03) — mode=overview|insight 분기 ────────────────
# Phase 3 PR 3 (2026-05-03) — mode=overview|insight branch.


@pytest.fixture
def mock_insight_success():
    """insight_narrative 성공 응답 mock — async (AsyncMock).
    Mock for insight_narrative success response — async (AsyncMock).
    """
    fake_data = {
        "positive_highlights": ["좋은 결과"],
        "focus_areas": ["주의"],
        "key_metrics": [],
        "next_actions": ["다음"],
        "status": "success",
        "generated_at": "2026-05-03T00:00:00Z",
        "days": 7,
    }
    with patch(
        "src.ui.routes.dashboard.dashboard_service.insight_narrative",
        new=AsyncMock(return_value=fake_data),
    ) as mock:
        yield mock


def test_dashboard_default_mode_is_overview():
    """mode 미지정 → 기존 overview 동작 보존 + 컨텍스트 mode='overview'.
    No mode param → preserves existing overview behavior + context mode='overview'.

    회귀 가드 — Phase 3 PR 3 의 mode 분기 도입이 기존 동작 깨지 않음 검증.
    """
    client = TestClient(app)
    mock_db = MagicMock()
    captured: dict = {}

    def _capture(request, template_name, context, **kwargs):
        captured.update(context)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>x</html>", status_code=200)

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value={"avg_score": {"value": 80}}) as mock_kpi, \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": False, "count": 0, "recent_analysis": None}), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard")

    assert response.status_code == 200
    # overview 분기 → dashboard_kpi 가 호출돼야 함 (insight 분기에서는 호출 안 됨)
    assert mock_kpi.called, "default mode=overview 시 dashboard_kpi 호출 누락"
    # 컨텍스트에 mode='overview' 키 주입 (Phase 3 PR 3 신규 요구사항)
    assert captured.get("mode") == "overview", \
        f"default mode 컨텍스트 'overview' 기대, 실제: {captured.get('mode')!r}"


def test_dashboard_mode_overview_explicit():
    """mode=overview 명시 시 default 와 동일하게 KPI 카드 렌더링 + mode 키.
    Explicit mode=overview behaves identically to default + mode key.
    """
    client = TestClient(app)
    mock_db = MagicMock()
    captured: dict = {}

    def _capture(request, template_name, context, **kwargs):
        captured.update(context)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>x</html>", status_code=200)

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value={"avg_score": {"value": 75}}) as mock_kpi, \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": False, "count": 0, "recent_analysis": None}), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard?mode=overview")

    assert response.status_code == 200
    assert mock_kpi.called, "mode=overview 명시 시 dashboard_kpi 호출 누락"
    assert captured.get("mode") == "overview", \
        f"mode=overview 컨텍스트 키 'overview' 기대, 실제: {captured.get('mode')!r}"


def test_dashboard_mode_insight_calls_narrative(mock_insight_success):
    """mode=insight → insight_narrative (async) 호출 + 응답 200.
    mode=insight → insight_narrative (async) called + 200 response.

    핵심 검증:
    - insight_narrative 가 정확히 1회 await 됨
    - 응답 본문 또는 컨텍스트에 insight 데이터 흔적 존재 (positive_highlights 등)
    """
    client = TestClient(app)
    mock_db = MagicMock()
    captured: dict = {}

    def _capture(request, template_name, context, **kwargs):
        captured.update(context)
        from fastapi.responses import HTMLResponse
        # 컨텍스트의 insight.positive_highlights 흔적을 응답에 노출 — 검증 보조
        # Expose insight.positive_highlights trace in response body — verification aid.
        body = "<html>insight</html>"
        insight = context.get("insight")
        if insight and insight.get("positive_highlights"):
            body = f"<html>insight: {insight['positive_highlights'][0]}</html>"
        return HTMLResponse(content=body, status_code=200)

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard?mode=insight")

    assert response.status_code == 200
    # insight_narrative 가 정확히 1회 await 됨 (overview 분기에서는 호출 안 됨)
    mock_insight_success.assert_awaited_once()
    # 컨텍스트에 insight 키 + mode=insight 주입
    assert captured.get("mode") == "insight", f"mode 컨텍스트 키 'insight' 기대, 실제: {captured.get('mode')!r}"
    assert "insight" in captured, "context 에 insight 키 누락"
    assert captured["insight"]["positive_highlights"] == ["좋은 결과"]
    # 응답 본문에 insight 데이터 노출 (템플릿 렌더 결과 흔적)
    assert "좋은 결과" in response.text


def test_dashboard_invalid_mode_falls_back_to_overview():
    """whitelist 외 mode 값 → overview 로 fallback (KPI 카드 렌더링).
    Mode value not in whitelist → falls back to overview (KPI cards rendered).

    보안 검증 — mode 파라미터의 임의 값 주입은 default 분기로 흡수.
    """
    client = TestClient(app)
    mock_db = MagicMock()
    captured: dict = {}

    def _capture(request, template_name, context, **kwargs):
        captured.update(context)
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content="<html>x</html>", status_code=200)

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value={"avg_score": {"value": 70}}) as mock_kpi, \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value={}), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": False, "count": 0, "recent_analysis": None}), \
         patch("src.ui.routes.dashboard.dashboard_service.insight_narrative", new=AsyncMock()) as mock_insight, \
         patch("src.ui.routes.dashboard.templates.TemplateResponse", side_effect=_capture):
        response = client.get("/dashboard?mode=invalid_value")

    assert response.status_code == 200
    # invalid mode → overview fallback → dashboard_kpi 호출 + insight_narrative 미호출
    assert mock_kpi.called, "invalid mode 시 overview fallback (dashboard_kpi 호출) 누락"
    mock_insight.assert_not_awaited()
    # 컨텍스트 mode 도 'overview' 로 정규화 (whitelist 외 값 → overview)
    assert captured.get("mode") == "overview", \
        f"invalid mode → 'overview' 정규화 기대, 실제: {captured.get('mode')!r}"


def test_dashboard_mode_toggle_links_present():
    """모드 토글 UI 링크 2건 (overview / insight) 응답 본문에 존재.
    Mode toggle UI links (overview / insight) present in response body.

    UI 정합성 — 사용자가 모드 전환 가능해야 함. 링크 형식은 유연하게 검증
    (querystring 또는 data attribute 모두 수용).
    """
    client = TestClient(app)
    mock_db = MagicMock()

    # 실제 템플릿을 렌더하기 위해 TemplateResponse mock X (실제 dashboard.html 사용).
    # Use real template render — TemplateResponse not mocked.
    # Jinja UndefinedError 회피 위해 모든 KPI 필드 (delta 포함) 명시.
    # Provide all KPI fields (incl. delta) to avoid Jinja UndefinedError.
    fake_kpi = {
        "avg_score": {"value": 80, "grade": "B", "delta": 0},
        "analysis_count": {"value": 0, "delta": 0},
        "high_security_issues": {"value": 0, "delta": 0},
        "active_repos": {"value": 0, "total": 0, "delta": 0},
    }
    fake_auto_merge = {
        "value": None,
        "final_success_rate_pct": None,
        "delta": None,
        "distinct_prs": 0,
        "final_success_prs": 0,
        "attempts": 0,
        "successes": 0,
    }

    with patch("src.ui.routes.dashboard.SessionLocal", return_value=_ctx(mock_db)), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_kpi", return_value=fake_kpi), \
         patch("src.ui.routes.dashboard.dashboard_service.dashboard_trend", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.frequent_issues_v2", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.auto_merge_kpi", return_value=fake_auto_merge), \
         patch("src.ui.routes.dashboard.dashboard_service.merge_failure_distribution", return_value=[]), \
         patch("src.ui.routes.dashboard.dashboard_service.feedback_status", return_value={"show_cta": False, "count": 0, "recent_analysis": None}):
        response = client.get("/dashboard")

    assert response.status_code == 200
    body = response.text

    # overview 토글 — href 또는 data-mode 형식 허용
    has_overview_link = (
        "mode=overview" in body
        or 'data-mode="overview"' in body
        or "data-mode='overview'" in body
    )
    # insight 토글 — href 또는 data-mode 형식 허용
    has_insight_link = (
        "mode=insight" in body
        or 'data-mode="insight"' in body
        or "data-mode='insight'" in body
    )

    assert has_overview_link, "응답 본문에 overview 모드 토글 링크 누락 (mode=overview 또는 data-mode='overview')"
    assert has_insight_link, "응답 본문에 insight 모드 토글 링크 누락 (mode=insight 또는 data-mode='insight')"
