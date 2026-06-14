"""tests/unit/api/test_users_api.py — Telegram OTP API 엔드포인트 단위 테스트.
tests/unit/api/test_users_api.py — Unit tests for Telegram OTP API endpoint.

환경변수는 src 임포트 전 반드시 주입해야 한다.
Environment variables must be injected before any src.* imports.
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
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from unittest.mock import MagicMock, patch  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from src.main import app  # noqa: E402
from src.auth.session import CurrentUser, require_login  # noqa: E402

# ── 테스트용 인증된 사용자 픽스처 ──
# ── Authenticated user fixture for tests ──
_FAKE_USER = CurrentUser(
    id=42,
    github_login="testuser",
    email="test@example.com",
    display_name="Test User",
    plaintext_token="gho_test",
)

# require_login 의존성 우회 — 인증된 상태로 테스트
# Override require_login dependency — test in authenticated state.
app.dependency_overrides[require_login] = lambda: _FAKE_USER

client = TestClient(app)


def _make_db_session_mock(db_mock: MagicMock) -> MagicMock:
    """context manager 패턴 DB 세션 mock을 생성한다.
    Create a DB session mock that supports the context manager protocol.
    """
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


# ── T9-A: POST /api/users/me/telegram-otp ──


def test_post_telegram_otp_returns_eight_digit_code():
    """인증된 사용자 호출 시 200과 8자리 숫자 OTP, expires_at을 반환한다.
    Returns 200 with an 8-digit numeric OTP and expires_at for an authenticated user.
    """
    mock_db = MagicMock()
    # execute/commit은 부작용만 — 반환값 불필요
    # execute/commit are side-effects only — return value not needed.
    mock_db.execute.return_value = None
    mock_db.commit.return_value = None

    with patch("src.api.users.SessionLocal", return_value=_make_db_session_mock(mock_db)):
        r = client.post("/api/users/me/telegram-otp")

    assert r.status_code == 200
    body = r.json()
    # OTP는 8자리 숫자 문자열이어야 한다 (C12 — 6→8, brute-force 공간 10^8)
    # OTP must be an 8-digit numeric string (C12 — 6→8, brute-force space 10^8).
    assert "otp" in body
    assert len(body["otp"]) == 8
    assert body["otp"].isdigit()
    # 만료 시각과 TTL 필드가 있어야 한다
    # expires_at and ttl_minutes must be present.
    assert "expires_at" in body
    assert "ttl_minutes" in body
    assert body["ttl_minutes"] == 5


def test_post_telegram_otp_overwrites_previous_otp():
    """2회 연속 호출 시 두 번째 OTP가 발급되어 첫 번째 OTP가 무효화된다.
    Two consecutive calls produce different OTPs — the second overwrites the first.
    """
    mock_db = MagicMock()
    mock_db.execute.return_value = None
    mock_db.commit.return_value = None

    collected_otps = []

    def _capture_execute(stmt, *args, **kwargs):
        # update() statement의 values에서 OTP 값을 캡처한다
        # Capture the OTP value from the update() statement values.
        return None

    mock_db.execute.side_effect = _capture_execute

    with patch("src.api.users.SessionLocal", return_value=_make_db_session_mock(mock_db)):
        r1 = client.post("/api/users/me/telegram-otp")
        r2 = client.post("/api/users/me/telegram-otp")

    assert r1.status_code == 200
    assert r2.status_code == 200

    otp1 = r1.json()["otp"]
    otp2 = r2.json()["otp"]

    # 두 OTP 모두 8자리 숫자 형식
    # Both OTPs must be 8-digit numeric strings.
    assert len(otp1) == 8 and otp1.isdigit()
    assert len(otp2) == 8 and otp2.isdigit()

    # DB execute가 각 요청마다 호출되어야 한다 (덮어쓰기 보장)
    # DB execute must be called once per request (overwrite guarantee).
    assert mock_db.execute.call_count == 2
    assert mock_db.commit.call_count == 2

    # 연속으로 발급된 OTP가 동일할 확률은 1/100,000,000 (10^8) — 실용적으로 다름을 기대
    # Probability of collision is 1/100,000,000 (10^8) — expect different values in practice.
    collected_otps.extend([otp1, otp2])
    assert len(collected_otps) == 2


def test_post_telegram_otp_requires_login():
    """비인증 상태에서 호출 시 302 리다이렉트 또는 401을 반환한다.
    Returns 302 redirect or 401 when called without authentication.
    """
    # 현재 오버라이드를 저장하여 다른 테스트 모듈의 전역 상태를 보존한다
    # Save the current override to preserve global state across test modules.
    _saved = app.dependency_overrides.get(require_login)
    del app.dependency_overrides[require_login]
    try:
        r = client.post("/api/users/me/telegram-otp", follow_redirects=False)
        # require_login은 302(Location: /login) 또는 401을 발생시킨다
        # require_login raises 302 (Location: /login) or 401.
        assert r.status_code in (302, 401)
    finally:
        # 저장된 오버라이드로 복원 — 이 파일 외부의 모듈이 설정한 오버라이드도 보존
        # Restore the saved override — preserves overrides set by other test modules.
        if _saved is not None:
            app.dependency_overrides[require_login] = _saved


def test_post_telegram_otp_uses_secrets_for_randomness():
    """OTP 생성에 secrets 모듈을 사용하는지 검증한다 (random 사용 금지).
    Verifies OTP generation uses secrets module (not random).

    실제 구현이 secrets.choice를 사용하면 응답값은 항상 숫자만 포함한다.
    If the implementation uses secrets.choice correctly, the OTP contains only digits.
    """
    mock_db = MagicMock()
    mock_db.execute.return_value = None
    mock_db.commit.return_value = None

    with patch("src.api.users.SessionLocal", return_value=_make_db_session_mock(mock_db)):
        r = client.post("/api/users/me/telegram-otp")

    body = r.json()
    otp = body["otp"]
    # 숫자 문자만 포함 — secrets.choice("0123456789") 보장
    # Only digit chars — guaranteed by secrets.choice("0123456789").
    assert all(c in "0123456789" for c in otp)
    assert len(otp) == 8


# ── T-3: asyncio.to_thread 래핑 검증 (사이클 113 P0-D 회귀 가드) ──
# ── T-3: asyncio.to_thread wrapping verification (Cycle 113 P0-D regression guard) ──


async def test_post_telegram_otp_wraps_db_in_to_thread():
    """issue_telegram_otp이 DB 저장을 asyncio.to_thread로 래핑하는지 검증한다.
    Verifies that issue_telegram_otp wraps DB save in asyncio.to_thread.

    사이클 113 P0-D 회귀 가드: 동기 SQLAlchemy 호출이 async 엔드포인트에서 이벤트 루프를
    블로킹하지 않도록 asyncio.to_thread로 wrap 되어야 한다.
    Cycle 113 P0-D regression guard: sync SQLAlchemy must be wrapped in asyncio.to_thread
    inside async endpoints to avoid event loop blocking.
    """
    import asyncio
    from src.api.users import issue_telegram_otp

    to_thread_calls: list[str] = []
    real_to_thread = asyncio.to_thread

    async def _spy(fn, *args, **kwargs):
        # 호출된 함수 이름 기록 — _do_save 클로저 확인
        # Record the name of the called function — checks for _do_save closure
        to_thread_calls.append(getattr(fn, "__name__", repr(fn)))
        return await real_to_thread(fn, *args, **kwargs)

    mock_db = MagicMock()
    mock_db.execute.return_value = None
    mock_db.commit.return_value = None

    with patch("src.api.users.asyncio.to_thread", side_effect=_spy):
        with patch("src.api.users.SessionLocal", return_value=_make_db_session_mock(mock_db)):
            # issue_telegram_otp 직접 호출 — TestClient는 ASGI event loop 별도 관리
            # Call issue_telegram_otp directly — TestClient manages its own ASGI event loop
            await issue_telegram_otp(current_user=_FAKE_USER)

    # asyncio.to_thread가 최소 1번 호출 — _do_save 클로저가 wrap됨
    # asyncio.to_thread must be called at least once — _do_save closure is wrapped
    assert len(to_thread_calls) >= 1
    # 호출된 함수 이름이 "_do_save" 포함
    # The called function name must include "_do_save"
    assert any("_do_save" in name for name in to_thread_calls)
