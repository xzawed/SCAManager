"""settings 페이지 stale webhook 배너 단위 테스트 (Phase 12 T12).
Unit tests for the stale webhook banner on the settings page (Phase 12 T12).
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-that-is-at-least-32-chars")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from src.main import app  # noqa: E402
from src.auth.session import require_login  # noqa: E402
from src.models.user import User as UserModel  # noqa: E402

_test_user = UserModel(
    id=1, github_id="12345", github_login="testuser",
    github_access_token="gho_test", email="test@example.com", display_name="Test User",
)
app.dependency_overrides[require_login] = lambda: _test_user

client = TestClient(app, raise_server_exceptions=True)


def _make_db_ctx(repo_webhook_id=42):
    """DB 컨텍스트 매니저 mock 생성.
    Create a mock DB context manager.
    """
    mock_db = MagicMock()
    # get_accessible_repo → returns repo (user_id=None 으로 모든 사용자 접근 허용)
    # get_accessible_repo → repo with user_id=None allows any logged-in user
    mock_repo = MagicMock(id=1, full_name="owner/repo", user_id=None, webhook_id=repo_webhook_id)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo

    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=mock_db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _make_config_orm():
    """RepoConfig ORM mock — railway_webhook_token 포함.
    RepoConfig ORM mock including railway_webhook_token.
    """
    return MagicMock(
        railway_webhook_token="rwt_test",
        railway_api_token=None,
    )


def _settings_get(stale: bool, repo_webhook_id: int = 42):
    """공통 GET /repos/owner/repo/settings 요청 헬퍼.
    Shared helper to GET /repos/owner/repo/settings.
    """
    from src.config_manager.manager import RepoConfigData  # pylint: disable=import-outside-toplevel

    with patch("src.ui.routes.settings.SessionLocal", return_value=_make_db_ctx(repo_webhook_id)), \
         patch("src.ui.routes.settings.get_repo_config",
               return_value=RepoConfigData(repo_full_name="owner/repo")), \
         patch("src.repositories.repo_config_repo.find_by_full_name",
               return_value=_make_config_orm()), \
         patch(
             "src.ui.routes.settings._detect_stale_webhook",
             new_callable=AsyncMock,
             return_value=stale,
         ):
        return client.get("/repos/owner%2Frepo/settings")


def test_settings_shows_stale_banner_when_check_suite_missing():
    """check_suite 없는 webhook → 배너 표시.
    Shows stale webhook banner when check_suite is not in webhook events.
    """
    resp = _settings_get(stale=True)

    assert resp.status_code == 200
    # 배너가 표시되어야 함 — check_suite 관련 텍스트 또는 배너 id 확인
    # Banner must be visible — verify check_suite text or banner element id
    assert "webhookStaleBanner" in resp.text or "check_suite" in resp.text or "재등록" in resp.text


def test_settings_no_banner_when_check_suite_present():
    """check_suite 구독 중인 webhook → 배너 미표시.
    No stale webhook banner when check_suite is already subscribed.
    """
    resp = _settings_get(stale=False)

    assert resp.status_code == 200
    # 배너가 없어야 함 — 배너 element id 가 HTML에 없어야 함
    # Banner must be absent — banner element id should not appear in HTML
    assert "webhookStaleBanner" not in resp.text
