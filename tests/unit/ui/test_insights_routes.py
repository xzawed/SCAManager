"""GET /insights UI 라우트 테스트 (compare + leaderboard 패널).
Tests for GET /insights UI route (compare + leaderboard panels).

Note: GET /insights/me 라우트는 Phase 1 PR 2 (2026-05-02) 에서 폐기.
회귀 가드는 tests/unit/services/test_analytics_service_deprecations.py 참조.

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

from contextlib import contextmanager  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.main import app  # noqa: E402
from src.auth.session import CurrentUser, require_login  # noqa: E402
from src.database import Base  # noqa: E402
from src.models.repository import Repository  # noqa: E402
from src.models.user import User  # noqa: E402

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


# ─── /insights/me (insights_me) — 폐기 (Phase 1 PR 2, 2026-05-02) ──────────
# 회귀 가드는 tests/unit/services/test_analytics_service_deprecations.py 참조.
# Removed in Phase 1 PR 2; regression guard moved to test_analytics_service_deprecations.py.


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


def test_insights_page_no_ormattr_error_on_real_db():
    """/insights 가 실제 SQLite 세션을 사용할 때 AttributeError 없이 200 을 반환해야 한다.
    /insights must return 200 without AttributeError when using a real SQLite session.

    Repository.config 같은 존재하지 않는 ORM 속성 접근을 방지하는 회귀 테스트.
    Regression guard: prevents accessing non-existent ORM attributes like Repository.config.
    """
    # in-memory SQLite 엔진 — StaticPool + check_same_thread=False 로 TestClient 스레드 안전 보장
    # StaticPool + check_same_thread=False ensures the same connection is shared across threads
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    with Session(engine) as seed_db:
        u = User(github_id=42, github_login="testuser", email="t@x.com", display_name="T")
        seed_db.add(u)
        seed_db.commit()
        seed_db.refresh(u)
        r = Repository(full_name="owner/test-repo", user_id=u.id)
        seed_db.add(r)
        seed_db.commit()

    @contextmanager
    def _real_session():
        with Session(engine) as s:
            yield s

    _prev_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    try:
        client = TestClient(app)
        with patch("src.ui.routes.insights.SessionLocal", side_effect=_real_session), \
             patch("src.ui.routes.insights.templates.TemplateResponse") as mock_tr:
            from fastapi.responses import HTMLResponse
            mock_tr.return_value = HTMLResponse(content="<html>ok</html>", status_code=200)
            response = client.get("/insights")

        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code} — ORM 속성 오류 또는 DB 쿼리 실패 가능성"
        )
    finally:
        if _prev_login is not None:
            app.dependency_overrides[require_login] = _prev_login
        else:
            app.dependency_overrides.pop(require_login, None)
        engine.dispose()


def test_insights_comparison_context_includes_leaderboard():
    """/insights 응답 컨텍스트에 leaderboard 키가 포함되어야 한다.
    The /insights template context must include a 'leaderboard' key.
    """
    _prev_login = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: _test_user
    try:
        client = TestClient(app)
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

        fake_leaderboard = [{"author_login": "alice", "avg_score": 88.0, "count": 3}]

        captured_context: dict = {}

        def _capture_response(request, template_name, context, **kwargs):
            captured_context.update(context)
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content="<html>ok</html>", status_code=200)

        with patch("src.ui.routes.insights.SessionLocal", return_value=_ctx(mock_db)), \
             patch("src.ui.routes.insights.analytics_service.repo_comparison", return_value=[]), \
             patch("src.ui.routes.insights.analytics_service.leaderboard", return_value=fake_leaderboard), \
             patch("src.ui.routes.insights.templates.TemplateResponse", side_effect=_capture_response):
            response = client.get("/insights")

        assert response.status_code == 200
        assert "leaderboard" in captured_context, (
            "'leaderboard' 키가 템플릿 컨텍스트에 없음 / 'leaderboard' key missing from template context"
        )
        assert captured_context["leaderboard"] == fake_leaderboard
    finally:
        if _prev_login is not None:
            app.dependency_overrides[require_login] = _prev_login
        else:
            app.dependency_overrides.pop(require_login, None)


# test_insights_me_context_includes_kpi — 폐기 (Phase 1 PR 2)
# /insights/me 라우트 자체가 폐기되어 kpi context 검증 불필요.
# Removed in Phase 1 PR 2; route gone, regression guard covers route 404.
