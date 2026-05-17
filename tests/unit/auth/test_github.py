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
# Verify route registration — only checks route existence, no OAuth external calls.
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
        # Capture the added User object but do not return it (prevents recursion).
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


# ---------------------------------------------------------------------------
# OAuth 리다이렉트 URI 보안 분기 — app_base_url 설정 여부
# ---------------------------------------------------------------------------

def test_auth_github_uses_app_base_url_when_set():
    """/auth/github — app_base_url 설정 시 고정 HTTPS URL을 redirect_uri로 사용한다."""
    with patch("src.auth.github.settings.app_base_url", "https://myapp.railway.app"):
        with patch("src.auth.github.oauth.github.authorize_redirect",
                   new_callable=AsyncMock, return_value=MagicMock(status_code=302)) as mock_redirect:
            client.get("/auth/github", follow_redirects=False)
            assert mock_redirect.called
            call_args = mock_redirect.call_args
            redirect_uri = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("redirect_uri")
            assert redirect_uri == "https://myapp.railway.app/auth/callback"


def test_auth_github_uses_url_for_when_app_base_url_not_set():
    """/auth/github — app_base_url 미설정 시 request.url_for로 redirect_uri를 생성한다."""
    with patch("src.auth.github.settings.app_base_url", ""):
        with patch("src.auth.github.oauth.github.authorize_redirect",
                   new_callable=AsyncMock, return_value=MagicMock(status_code=302)) as mock_redirect:
            client.get("/auth/github", follow_redirects=False)
            assert mock_redirect.called
            call_args = mock_redirect.call_args
            redirect_uri = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("redirect_uri")
            assert "auth/callback" in str(redirect_uri)


# ---------------------------------------------------------------------------
# OAuth 콜백 — 실패 경로
# ---------------------------------------------------------------------------

def test_callback_token_failure_returns_500():
    """authorize_access_token 실패 시 500 반환(미처리 예외 문서화)."""
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, side_effect=Exception("OAuth failed")):
        r = no_raise_client.get("/auth/callback?code=bad&state=bad", follow_redirects=False)
    assert r.status_code == 500


def test_callback_user_api_failure_returns_500():
    """GitHub user API 호출 실패 시 500 반환."""
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    mock_token = {"access_token": "gho_token"}
    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock, side_effect=Exception("GitHub API unavailable")):
            r = no_raise_client.get("/auth/callback?code=test&state=test", follow_redirects=False)
    assert r.status_code == 500


def test_callback_missing_user_id_returns_500():
    """user_info에 'id' 필드가 없으면 KeyError → 500 반환."""
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    mock_token = {"access_token": "gho_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {"login": "nouser"}  # id 없음
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = []
    with patch("src.auth.github.oauth.github.authorize_access_token",
               new_callable=AsyncMock, return_value=mock_token):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock, side_effect=[mock_user_info, mock_emails_resp]):
            with patch("src.auth.github.SessionLocal") as mock_sl:
                mock_sl.return_value.__enter__.return_value = MagicMock()
                r = no_raise_client.get("/auth/callback?code=test&state=test", follow_redirects=False)
    assert r.status_code == 500


# ---------------------------------------------------------------------------
# display_name fallback — name=None 또는 빈 문자열이면 login 사용
# ---------------------------------------------------------------------------

def test_callback_display_name_falls_back_to_login_when_name_none():
    """user_info['name']=None 인 경우 display_name은 github_login을 사용해야 한다."""
    from src.models.user import User
    mock_token = {"access_token": "gho_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 77777, "login": "loginonly", "name": None
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "login@example.com", "primary": True, "verified": True}
    ]
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    captured = {}

    def capture_add(obj):
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
    assert captured["user"].display_name == "loginonly"


def test_callback_display_name_falls_back_to_login_when_name_empty():
    """user_info['name']='' 인 경우 display_name은 github_login을 사용해야 한다."""
    from src.models.user import User
    mock_token = {"access_token": "gho_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 88888, "login": "emptyname", "name": ""
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "empty@example.com", "primary": True, "verified": True}
    ]
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    captured = {}

    def capture_add(obj):
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
    assert captured["user"].display_name == "emptyname"


# ---------------------------------------------------------------------------
# 보안: OAuth CSRF state 검증
# ---------------------------------------------------------------------------

def test_callback_without_prior_auth_session_fails():
    """/auth/github를 먼저 거치지 않은(state 없는) 직접 콜백 요청은 성공하지 않아야 한다.

    Authlib은 authorize_access_token() 내부에서 session state와 query state를 비교한다.
    prior /auth/github 없이 직접 /auth/callback에 접근하면 MismatchingStateError 등의 예외가 발생,
    500으로 응답해야 하며 절대로 302(/)로 성공 응답하면 안 된다.
    """
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    r = no_raise_client.get(
        "/auth/callback?code=legit_code&state=forged_state",
        follow_redirects=False,
    )
    # 성공(302 to /)이어서는 안 된다.
    # Must not be a success redirect (302 to /).
    assert not (r.status_code == 302 and r.headers.get("location") == "/"), (
        "CSRF 방어 실패: state 없는 직접 콜백이 성공 리다이렉트를 반환했다"
    )


def test_jinja2_autoescape_enabled():
    """FastAPI Jinja2Templates 인스턴스의 autoescape가 활성화되어야 한다.
    Jinja2Templates autoescape must be enabled (XSS protection).

    starlette >= 0.21 returns select_autoescape callable instead of True;
    both forms are valid — callable means HTML/XML files are autoescaped.
    """
    from fastapi.templating import Jinja2Templates
    t = Jinja2Templates(directory="src/templates")
    autoescape = t.env.autoescape
    # autoescape가 True(bool) 이거나 callable(select_autoescape) 이면 활성 상태
    # autoescape is active when it's True (bool) or a callable (select_autoescape)
    assert autoescape is True or callable(autoescape), (
        "Jinja2 autoescape가 비활성화되어 있어 XSS 위험이 있다 / "
        "Jinja2 autoescape is disabled — XSS risk"
    )


# ---------------------------------------------------------------------------
# OAuth scope 설정 검증
# OAuth scope configuration verification
# ---------------------------------------------------------------------------

def test_oauth_scope_configured_correctly():
    """GitHub OAuth 등록 시 scope가 'repo user:email'로 설정되어야 한다.
    GitHub OAuth must be registered with scope 'repo user:email'.
    """
    from src.auth.github import oauth
    scope = oauth.github.client_kwargs.get("scope")
    assert scope == "repo user:email"


# ---------------------------------------------------------------------------
# CSRF state 위조 — Authlib MismatchingStateError 명시적 단위 테스트
# CSRF state forgery — explicit MismatchingStateError unit test
# ---------------------------------------------------------------------------

def test_callback_mismatching_state_error_returns_500():
    """state 위조 시 MismatchingStateError → 500 반환 (CSRF 방어 명시적 검증).
    Forged state causes MismatchingStateError → 500 (explicit CSRF defence).
    """
    # 실제 Authlib import 경로 확인 후 사용
    # Use the verified Authlib import path
    try:
        from authlib.integrations.base_client.errors import MismatchingStateError
    except ImportError:
        from authlib.common.errors import AuthlibBaseError as MismatchingStateError

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    with patch(
        "src.auth.github.oauth.github.authorize_access_token",
        new_callable=AsyncMock,
        side_effect=MismatchingStateError(),
    ):
        r = no_raise_client.get(
            "/auth/callback?code=x&state=forged_state",
            follow_redirects=False,
        )
    # 성공(302 to /)이어서는 안 된다
    # Must not be a success redirect
    assert r.status_code == 500


def test_callback_missing_state_returns_error():
    """state 파라미터 없이 code만 있는 콜백 → 성공 302(/) 아님.
    Code-only callback without state must not produce a success redirect.
    """
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    r = no_raise_client.get(
        "/auth/callback?code=only_code_no_state",
        follow_redirects=False,
    )
    # 성공(302 to /)이어서는 안 된다
    # Must not be a success redirect (302 to /).
    assert not (r.status_code == 302 and r.headers.get("location") == "/")


# ---------------------------------------------------------------------------
# Session fixation 방어 — 인증 완료 후 세션 초기화 순서 검증
# Session fixation defence — session cleared before setting user_id
# ---------------------------------------------------------------------------

def test_callback_clears_session_before_setting_user_id():
    """인증 완료 후 session.clear() 가 user_id 설정보다 먼저 호출되어야 한다.
    session.clear() must be called before session['user_id'] is set.
    """
    from src.models.user import User  # noqa: PLC0415

    mock_token = {"access_token": "gho_token"}
    mock_user_info = MagicMock()
    mock_user_info.json.return_value = {
        "id": 55555, "login": "fixuser", "name": "Fix User",
    }
    mock_emails_resp = MagicMock()
    mock_emails_resp.json.return_value = [
        {"email": "fix@example.com", "primary": True, "verified": True}
    ]
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    call_order: list[str] = []

    class TrackingDict(dict):
        # 호출 순서 추적용 dict 서브클래스
        # Dict subclass to track call order for session fixation verification.
        def clear(self):
            call_order.append("clear")
            super().clear()

        def __setitem__(self, key, value):
            call_order.append(f"set:{key}")
            super().__setitem__(key, value)

    tracking_session = TrackingDict()

    async def patched_authorize(request):
        # 세션을 TrackingDict로 교체하여 호출 순서 추적
        # Replace session with TrackingDict to track call order
        request.scope["session"] = tracking_session
        return mock_token

    with patch("src.auth.github.oauth.github.authorize_access_token",
               side_effect=patched_authorize):
        with patch("src.auth.github.oauth.github.get",
                   new_callable=AsyncMock,
                   side_effect=[mock_user_info, mock_emails_resp]):
            with patch("src.auth.github.SessionLocal") as mock_sl:
                mock_db.query.return_value.filter.return_value.first.return_value = None
                mock_sl.return_value.__enter__.return_value = mock_db
                client.get("/auth/callback?code=test&state=test", follow_redirects=False)

    # clear()가 먼저, user_id 설정이 나중
    # clear() must come before set:user_id
    assert "clear" in call_order, "session.clear() 가 호출되지 않았다"
    assert "set:user_id" in call_order, "session['user_id'] 가 설정되지 않았다"
    clear_idx = call_order.index("clear")
    userid_idx = call_order.index("set:user_id")
    assert clear_idx < userid_idx, (
        f"session.clear()({clear_idx}) 가 user_id 설정({userid_idx}) 이후에 호출됐다 — session fixation 방어 실패"
    )


# ---------------------------------------------------------------------------
# OAuthError — access_denied 등 OAuth 에러 처리
# OAuthError — handling OAuth errors such as access_denied
# ---------------------------------------------------------------------------

def test_callback_oauth_error_returns_non_success():
    """OAuthError(access_denied) 발생 시 성공 302(/)가 아닌 응답을 반환해야 한다.
    OAuthError (e.g. access_denied) must not produce a success redirect.
    """
    try:
        from authlib.integrations.base_client.errors import OAuthError
    except ImportError:
        from authlib.common.errors import AuthlibBaseError as OAuthError

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    with patch(
        "src.auth.github.oauth.github.authorize_access_token",
        new_callable=AsyncMock,
        side_effect=OAuthError(error="access_denied"),
    ):
        r = no_raise_client.get(
            "/auth/callback?code=x&state=x",
            follow_redirects=False,
        )
    # 성공(302 to /)이어서는 안 된다
    # Must not be a success redirect.
    assert not (r.status_code == 302 and r.headers.get("location") == "/")
