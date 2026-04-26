"""TDD Red — GET /insights 및 GET /insights/me UI 라우트 테스트.
TDD Red — Tests for GET /insights and GET /insights/me UI routes.

src/ui/routes/insights.py 는 아직 존재하지 않으므로,
이 테스트 모음은 전부 실패해야 한다 (ImportError 또는 404).
Since src/ui/routes/insights.py does not yet exist,
all tests in this suite must fail (ImportError or 404).
"""
import os

# 환경변수 주입 — src 모듈 import 이전에 반드시 선행
# Inject env vars before any src.* import triggers Settings()
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402
from src.auth.session import CurrentUser, require_login  # noqa: E402

# 로그인 사용자 픽스처 — CurrentUser dataclass 사용 (User ORM 모델 아님)
# Test user fixture — use CurrentUser dataclass (not the User ORM model)
_test_user = CurrentUser(
    id=1,
    github_login="testuser",
    email="test@example.com",
    display_name="Test User",
    plaintext_token="gho_test",
    is_telegram_connected=False,
)


def _ctx(db_mock: MagicMock) -> MagicMock:
    """SessionLocal() 컨텍스트 매니저를 흉내내는 헬퍼.
    Helper that mimics the SessionLocal() context manager.
    """
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_insights_page_requires_login():
    """비로그인 상태에서 GET /insights 는 302 리다이렉트 또는 비-200 응답을 반환해야 한다.
    Without login override, GET /insights must redirect (302) or return a non-200 status.

    require_login 미재정의 상태 → /login 으로 302 리다이렉트 발생.
    Without dependency override → 302 redirect to /login.
    """
    # require_login 재정의가 없으면 302 리다이렉트 발생
    # Remove any existing override so the real require_login runs
    overrides_backup = dict(app.dependency_overrides)
    app.dependency_overrides.pop(require_login, None)
    try:
        client = TestClient(app, follow_redirects=False)
        response = client.get("/insights")
        # 라우트가 존재하면 비로그인 → 302, 라우트 없으면 404 — 둘 다 비-200
        # If route exists: 302 redirect; if route missing: 404 — both are non-200
        assert response.status_code != 200, (
            f"Expected non-200 (login redirect or 404), got {response.status_code}"
        )
    finally:
        # 다른 테스트 영향 방지를 위해 원본 overrides 복원
        # Restore overrides so other tests are not affected
        app.dependency_overrides.clear()
        app.dependency_overrides.update(overrides_backup)


def test_insights_page_returns_200():
    """로그인 상태 + mock DB + mock analytics_service → GET /insights 는 200을 반환해야 한다.
    With login override, mocked DB and analytics_service → GET /insights returns 200.

    analytics_service.repo_comparison 과 TemplateResponse 를 모킹하여
    템플릿 파일 없이도 200 검증 가능.
    Mock repo_comparison and TemplateResponse to validate 200 without template files.
    """
    # 기존 require_login override 저장 후 교체 — 타 모듈의 모듈-레벨 설정 보호
    # Save previous require_login override to protect module-level setups in other test modules
    _prev_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    try:
        client = TestClient(app)
        mock_db = MagicMock()
        # 사용자 접근 가능한 리포 목록 — all_repos 쿼리용
        # Repository list for the all_repos query
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        fake_comparison = [
            {"repo_id": 1, "full_name": "owner/repo", "avg_score": 85.0, "count": 10}
        ]

        with patch("src.ui.routes.insights.SessionLocal", return_value=_ctx(mock_db)), \
             patch(
                 "src.ui.routes.insights.analytics_service.repo_comparison",
                 return_value=fake_comparison,
             ), \
             patch("src.ui.routes.insights.templates.TemplateResponse") as mock_tr:
            # TemplateResponse 는 FastAPI Response 처럼 동작해야 함
            # TemplateResponse must behave like a FastAPI Response
            from fastapi.responses import HTMLResponse
            mock_tr.return_value = HTMLResponse(content="<html>insights</html>", status_code=200)
            response = client.get("/insights")

        # 라우트가 구현되면 200, 아직 없으면 404 — Red 단계에서는 404
        # 200 when route is implemented; 404 in Red phase
        assert response.status_code == 200, (
            f"Expected 200 after implementation, got {response.status_code} "
            f"(route not yet implemented — this test must FAIL in Red phase)"
        )
    finally:
        # 이전 값이 있었으면 복원, 없었으면 제거 — 타 모듈 격리 보장
        # Restore previous value if it existed, otherwise remove — ensures cross-module isolation
        if _prev_login is not None:
            app.dependency_overrides[require_login] = _prev_login
        else:
            app.dependency_overrides.pop(require_login, None)


def test_insights_me_returns_200():
    """로그인 상태 + mock analytics_service.author_trend → GET /insights/me 는 200을 반환해야 한다.
    With login override and mocked author_trend → GET /insights/me returns 200.

    TemplateResponse 를 모킹하여 templates/insights_me.html 없이도 동작 검증.
    Mock TemplateResponse so insights_me.html template absence does not block validation.
    """
    _prev_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    try:
        client = TestClient(app)

        fake_trend = [
            {"date": "2026-04-01", "avg_score": 82.0, "count": 3},
            {"date": "2026-04-02", "avg_score": 88.5, "count": 2},
        ]

        with patch(
            "src.ui.routes.insights.analytics_service.author_trend",
            return_value=fake_trend,
        ) as mock_trend, \
             patch("src.ui.routes.insights.templates.TemplateResponse") as mock_tr:
            from fastapi.responses import HTMLResponse
            mock_tr.return_value = HTMLResponse(content="<html>me</html>", status_code=200)
            response = client.get("/insights/me")

        # Red 단계 — 라우트 미구현 시 404 로 실패
        # Red phase — 404 expected until route is implemented
        assert response.status_code == 200, (
            f"Expected 200 after implementation, got {response.status_code} "
            f"(route not yet implemented — this test must FAIL in Red phase)"
        )
    finally:
        if _prev_login is not None:
            app.dependency_overrides[require_login] = _prev_login
        else:
            app.dependency_overrides.pop(require_login, None)


def test_insights_me_respects_days_param():
    """GET /insights/me?days=7 → analytics_service.author_trend 가 days=7 로 호출되어야 한다.
    GET /insights/me?days=7 must call analytics_service.author_trend with days=7.

    days 쿼리 파라미터가 서비스 계층까지 올바르게 전달되는지 검증.
    Verifies that the days query param is correctly forwarded to the service layer.
    """
    _prev_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    try:
        client = TestClient(app)

        with patch(
            "src.ui.routes.insights.analytics_service.author_trend",
            return_value=[],
        ) as mock_trend, \
             patch("src.ui.routes.insights.templates.TemplateResponse") as mock_tr:
            from fastapi.responses import HTMLResponse
            mock_tr.return_value = HTMLResponse(content="<html>me</html>", status_code=200)
            response = client.get("/insights/me?days=7")

        # days=7 파라미터가 author_trend 에 전달됐는지 확인
        # Verify days=7 was forwarded to author_trend
        if response.status_code == 200:
            # 라우트 구현 후 검증: author_trend 호출 인자에 days=7 포함
            # After implementation: assert author_trend was called with days=7
            assert mock_trend.called, "author_trend must be called"
            call_kwargs = mock_trend.call_args
            # positional 또는 keyword 인자 중 days=7 확인
            # days=7 must appear as positional or keyword argument
            days_passed = (
                call_kwargs.kwargs.get("days")
                if call_kwargs.kwargs
                else (call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
            )
            assert days_passed == 7, f"Expected days=7, got {days_passed}"
        else:
            # Red 단계 — 라우트가 없으면 404 로 실패 (의도된 동작)
            # Red phase — 404 means route is not implemented yet (expected failure)
            assert response.status_code == 200, (
                f"Route not implemented yet — expected failure in Red phase, "
                f"got {response.status_code}"
            )
    finally:
        if _prev_login is not None:
            app.dependency_overrides[require_login] = _prev_login
        else:
            app.dependency_overrides.pop(require_login, None)


def test_insights_page_with_repos_param_returns_200():
    """repos 파라미터가 있을 때 비교 데이터를 포함하여 200을 반환해야 한다.
    With repos param, /insights should return 200 and call repo_comparison."""
    _prev_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    try:
        client = TestClient(app)
        mock_db = MagicMock()
        mock_repo = MagicMock()
        mock_repo.id = 10
        mock_repo.full_name = "owner/myrepo"
        # 첫 번째 쿼리(selected_repos)와 두 번째(all_repos) 모두 같은 mock 반환
        # Both selected_repos and all_repos queries return same mock for simplicity
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_repo]
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        fake_comparison = [{"repo_id": 10, "avg_score": 88.0, "count": 4}]

        with patch("src.ui.routes.insights.SessionLocal", return_value=_ctx(mock_db)), \
             patch(
                 "src.ui.routes.insights.analytics_service.repo_comparison",
                 return_value=fake_comparison,
             ), \
             patch("src.ui.routes.insights.templates.TemplateResponse") as mock_tr:
            from fastapi.responses import HTMLResponse
            mock_tr.return_value = HTMLResponse(content="<html>ok</html>", status_code=200)
            response = client.get("/insights?repos=owner%2Fmyrepo")

        assert response.status_code == 200
    finally:
        if _prev_login is not None:
            app.dependency_overrides[require_login] = _prev_login
        else:
            app.dependency_overrides.pop(require_login, None)
