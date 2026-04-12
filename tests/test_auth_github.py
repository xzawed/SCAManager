import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_login_page_loads():
    """GET /login은 로그인 페이지(200 HTML)를 반환한다."""
    with patch("src.auth.github.get_current_user", return_value=None):
        r = client.get("/login")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_login_redirects_if_already_authenticated():
    """이미 로그인된 사용자가 /login 접근 시 / 로 리다이렉트."""
    from src.models.user import User
    mock_user = User(id=1, github_id="12345", email="a@b.com", display_name="Test")
    with patch("src.auth.github.get_current_user", return_value=mock_user):
        r = client.get("/login", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/"


def test_logout_clears_session_and_redirects():
    """POST /auth/logout은 세션을 초기화하고 /login 으로 리다이렉트한다."""
    r = client.post("/auth/logout", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


def test_callback_creates_new_user_and_redirects():
    """콜백 처리 시 신규 유저를 생성하고 / 로 리다이렉트한다."""
    mock_token = {"access_token": "gho_new_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 99001,
        "login": "newuser",
        "name": "New User",
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "newuser@github.com", "primary": True, "verified": True}
    ]
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None  # 신규 유저

    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock,
                   side_effect=[mock_user_info, mock_emails_resp]):
            with patch("src.auth.github.SessionLocal") as mock_sl:
                mock_sl.return_value.__enter__.return_value = mock_db
                r = client.get(
                    "/auth/callback?code=test-code&state=test-state",
                    follow_redirects=False,
                )

    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert mock_db.add.called
    assert mock_db.commit.called


def test_callback_updates_existing_user_and_redirects():
    """콜백 처리 시 기존 유저의 토큰을 갱신하고 / 로 리다이렉트한다."""
    from src.models.user import User
    mock_token = {"access_token": "gho_updated_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 99002,
        "login": "existinguser",
        "name": "Existing User",
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "existing@github.com", "primary": True, "verified": True}
    ]
    existing_user = User(
        id=5,
        github_id="99002",
        github_login="existinguser",
        email="existing@github.com",
        display_name="Existing User",
    )
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing_user

    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock,
                   side_effect=[mock_user_info, mock_emails_resp]):
            with patch("src.auth.github.SessionLocal") as mock_sl:
                mock_sl.return_value.__enter__.return_value = mock_db
                r = client.get(
                    "/auth/callback?code=test-code&state=test-state",
                    follow_redirects=False,
                )

    assert r.status_code == 302
    assert r.headers["location"] == "/"
    assert not mock_db.add.called   # 기존 유저이므로 add 미호출
    assert existing_user.github_access_token == "gho_updated_token"


# ---------------------------------------------------------------------------
# 라우트 등록 확인 — OAuth 외부 연결 없이 라우트 존재 여부만 검증
# ---------------------------------------------------------------------------

def test_auth_github_route_exists():
    """/auth/github 라우트가 앱에 등록되어 있는지 확인한다."""
    from src.main import app  # noqa: PLC0415
    routes = [r.path for r in app.routes]
    assert "/auth/github" in routes


def test_auth_callback_route_exists():
    """/auth/callback 라우트가 앱에 등록되어 있는지 확인한다."""
    from src.main import app  # noqa: PLC0415
    routes = [r.path for r in app.routes]
    assert "/auth/callback" in routes


def test_logout_route_exists():
    """POST /auth/logout 라우트가 앱에 등록되어 있는지 확인한다."""
    from src.main import app  # noqa: PLC0415
    routes = [r.path for r in app.routes]
    assert "/auth/logout" in routes


def test_callback_no_primary_email_uses_fallback():
    """이메일 응답에 primary+verified 이메일이 없을 경우 user_info["email"]을 fallback으로 사용해야 한다."""
    from src.models.user import User  # noqa: PLC0415
    mock_token = {"access_token": "gho_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 12345, "login": "user", "name": "User", "email": "fallback@example.com"
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "notprimary@example.com", "primary": False, "verified": True}
    ]
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    captured = {}

    def capture_add(obj):
        # add된 User 객체를 캡처만 하고 반환하지 않는다 (재귀 방지)
        if isinstance(obj, User):
            captured["user"] = obj

    mock_db.add.side_effect = capture_add

    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock, side_effect=[mock_user_info, mock_emails_resp]):
            with patch("src.auth.github.SessionLocal") as mock_sl:
                mock_sl.return_value.__enter__.return_value = mock_db
                client.get("/auth/callback?code=test&state=test", follow_redirects=False)

    assert captured.get("user") is not None
    assert captured["user"].email == "fallback@example.com"
