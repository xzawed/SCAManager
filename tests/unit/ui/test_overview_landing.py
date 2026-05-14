"""GET / 라우트 — 인증 상태별 분기 테스트.
GET / route — branch by auth state tests.

검증:
- 미인증 → 200 landing.html 렌더링 (기존 302 /login 아님)
- 인증 → 200 overview.html 렌더링 (기존 동작 보존)
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

from src.auth.session import CurrentUser, get_current_user
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


def _tmpl_name(call_args) -> str:
    """TemplateResponse call_args 에서 template 이름 추출.
    Extract template name from TemplateResponse call_args.
    """
    if len(call_args.args) > 1:
        return call_args.args[1]
    return call_args.kwargs.get("name", "")


# ─── 미인증 → landing page ─────────────────────────────────────────────────


def test_root_shows_landing_for_unauthenticated():
    """미인증 GET / → 200 landing.html.
    Unauthenticated GET / → 200 landing.html (not 302 redirect).
    """
    app.dependency_overrides[get_current_user] = lambda: None
    try:
        with patch("src.ui.routes.overview.templates.TemplateResponse") as mock_tr:
            mock_tr.return_value = HTMLResponse(content="<html>landing</html>", status_code=200)
            client = TestClient(app, follow_redirects=False)
            response = client.get("/")

        assert response.status_code == 200, (
            f"미인증 시 200 기대, 실제: {response.status_code}"
        )
        assert mock_tr.called, "TemplateResponse 가 호출되지 않음"
        assert _tmpl_name(mock_tr.call_args) == "landing.html", (
            f"미인증 시 landing.html 기대, 실제: {_tmpl_name(mock_tr.call_args)!r}"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─── 인증 → overview 유지 ──────────────────────────────────────────────────


def test_root_shows_overview_for_authenticated():
    """인증 GET / → 200 overview.html (기존 동작 보존).
    Authenticated GET / → 200 overview.html (preserves existing behavior).
    """
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    mock_db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []

    app.dependency_overrides[get_current_user] = lambda: _TEST_USER
    try:
        with (
            patch("src.ui.routes.overview.SessionLocal", return_value=_ctx(mock_db)),
            patch(
                "src.ui.routes.overview.analysis_feedback_repo.get_calibration_by_score_range",
                return_value={},
            ),
            patch("src.ui.routes.overview.templates.TemplateResponse") as mock_tr,
        ):
            mock_tr.return_value = HTMLResponse(content="<html>overview</html>", status_code=200)
            client = TestClient(app, follow_redirects=False)
            response = client.get("/")

        assert response.status_code == 200, (
            f"인증 사용자 → 200 기대, 실제: {response.status_code}"
        )
        assert mock_tr.called, "인증 사용자 → TemplateResponse 호출 기대"
        assert _tmpl_name(mock_tr.call_args) == "overview.html", (
            f"인증 시 overview.html 기대, 실제: {_tmpl_name(mock_tr.call_args)!r}"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
