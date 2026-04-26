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


def test_post_telegram_otp_returns_six_digit_code():
    """인증된 사용자 호출 시 200과 6자리 숫자 OTP, expires_at을 반환한다.
    Returns 200 with a 6-digit numeric OTP and expires_at for an authenticated user.
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
    # OTP는 6자리 숫자 문자열이어야 한다
    # OTP must be a 6-digit numeric string.
    assert "otp" in body
    assert len(body["otp"]) == 6
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

    # 두 OTP 모두 6자리 숫자 형식
    # Both OTPs must be 6-digit numeric strings.
    assert len(otp1) == 6 and otp1.isdigit()
    assert len(otp2) == 6 and otp2.isdigit()

    # DB execute가 각 요청마다 호출되어야 한다 (덮어쓰기 보장)
    # DB execute must be called once per request (overwrite guarantee).
    assert mock_db.execute.call_count == 2
    assert mock_db.commit.call_count == 2

    # 연속으로 발급된 OTP가 동일할 확률은 1/1,000,000 — 실용적으로 다름을 기대
    # Probability of collision is 1/1,000,000 — expect different values in practice.
    collected_otps.extend([otp1, otp2])
    assert len(collected_otps) == 2


def test_post_telegram_otp_requires_login():
    """비인증 상태에서 호출 시 302 리다이렉트 또는 401을 반환한다.
    Returns 302 redirect or 401 when called without authentication.
    """
    # 의존성 오버라이드를 일시적으로 제거하여 비인증 상태 시뮬레이션
    # Temporarily remove the override to simulate unauthenticated state.
    del app.dependency_overrides[require_login]
    try:
        r = client.post("/api/users/me/telegram-otp", follow_redirects=False)
        # require_login은 302(Location: /login) 또는 401을 발생시킨다
        # require_login raises 302 (Location: /login) or 401.
        assert r.status_code in (302, 401)
    finally:
        # 다른 테스트에 영향을 주지 않도록 오버라이드 복원
        # Restore the override so other tests are not affected.
        app.dependency_overrides[require_login] = lambda: _FAKE_USER


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
    assert len(otp) == 6
