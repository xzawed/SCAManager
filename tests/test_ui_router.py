import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-csecret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app
from src.auth.session import require_login
from src.models.user import User as UserModel

# 모든 UI 테스트에서 require_login 의존성을 우회 (user_id=1 로그인 상태)
_test_user = UserModel(id=1, google_id="g-id-1", email="test@example.com", display_name="Test User")
app.dependency_overrides[require_login] = lambda: _test_user

client = TestClient(app)


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ── 비로그인 리다이렉트 테스트 ──────────────────────────

def test_overview_redirects_when_not_logged_in():
    """비로그인 상태에서 / 접근 시 /login 으로 302 리다이렉트."""
    del app.dependency_overrides[require_login]
    try:
        r = client.get("/", follow_redirects=False)
        assert r.status_code == 302
        assert "/login" in r.headers.get("location", "")
    finally:
        app.dependency_overrides[require_login] = lambda: _test_user


# ── 로그인 상태 기존 테스트 ──

def test_overview_returns_html():
    """로그인 후 / 는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_repo_detail_returns_html():
    """로그인 후 본인 리포 상세 페이지는 200 HTML을 반환한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200


def test_repo_detail_404():
    """존재하지 않는 리포 접근 시 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/nope%2Frepo")
    assert r.status_code == 404


def test_repo_detail_404_for_other_users_repo():
    """타인 소유 리포(user_id=2) 접근 시 404. 현재 사용자는 user_id=1."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=2, full_name="owner/repo", user_id=2
    )
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 404


def test_settings_returns_html():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, full_name="owner/repo", user_id=None
    )
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200


def test_post_settings_redirects():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "85",
                    "auto_reject_threshold": "55",
                    "notify_chat_id": "-123",
                    "n8n_webhook_url": "http://n8n.local/webhook/abc",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.n8n_webhook_url == "http://n8n.local/webhook/abc"
    assert r.status_code == 303


def test_post_settings_empty_n8n_url():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "disabled",
                    "auto_approve_threshold": "75",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.n8n_webhook_url == ""


def test_post_settings_with_auto_merge_checked():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "80",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                    "auto_merge": "on",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.auto_merge is True
    assert r.status_code == 303


def test_post_settings_without_auto_merge_checkbox():
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "80",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    assert called_config.auto_merge is False
    assert r.status_code == 303
