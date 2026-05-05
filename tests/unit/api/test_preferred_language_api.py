"""사용자 선호 언어 API 단위 테스트 (Phase 2 PR-4 사이클 84).

POST /api/users/me/preferred-language — DB + Cookie 동시 갱신 검증.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from src.api.users import PreferredLanguageUpdate, router
from fastapi import FastAPI


@pytest.fixture
def client():
    """TestClient with mocked auth dependency."""
    app = FastAPI()
    app.include_router(router)

    # Mock require_login dependency
    from src.auth.session import require_login

    def fake_user():
        return MagicMock(id=42, email="test@example.com")

    app.dependency_overrides[require_login] = fake_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_preferred_language_validator_valid_locale():
    """SUPPORTED_LOCALES 영역 (en/ko/ja) → 정규화 OK."""
    body = PreferredLanguageUpdate(language="en")
    assert body.language == "en"


def test_preferred_language_validator_normalizes_case():
    """대문자 입력 → 소문자 정규화."""
    body = PreferredLanguageUpdate(language="KO")
    assert body.language == "ko"


def test_preferred_language_validator_strips_whitespace():
    """공백 좌우 제거."""
    body = PreferredLanguageUpdate(language="  ja  ")
    assert body.language == "ja"


def test_preferred_language_validator_empty_raises():
    """빈 문자열 → ValueError."""
    with pytest.raises(ValueError, match="must not be empty"):
        PreferredLanguageUpdate(language="")


def test_preferred_language_validator_unsupported_raises():
    """미지원 locale (예: 'zh') → ValueError."""
    with pytest.raises(ValueError, match="not in SUPPORTED_LOCALES"):
        PreferredLanguageUpdate(language="zh")


def test_preferred_language_endpoint_updates_db_and_cookie(client):
    """POST 엔드포인트 = DB update + Cookie 설정 검증."""
    with patch("src.api.users.SessionLocal") as mock_session:
        db_mock = MagicMock()
        mock_session.return_value.__enter__.return_value = db_mock

        res = client.post(
            "/api/users/me/preferred-language",
            json={"language": "ja"},
        )

        assert res.status_code == 200
        data = res.json()
        assert data["language"] == "ja"
        assert "preferred language updated" in data["message"]

        # Cookie 검증 — preferred_language=ja
        assert "preferred_language" in res.cookies
        assert res.cookies["preferred_language"] == "ja"

        # DB update 호출 검증
        assert db_mock.execute.called
        assert db_mock.commit.called


def test_preferred_language_endpoint_invalid_returns_422(client):
    """미지원 locale → pydantic validation error 422."""
    res = client.post(
        "/api/users/me/preferred-language",
        json={"language": "fr"},
    )
    assert res.status_code == 422


def test_preferred_language_endpoint_kill_switch_returns_503(client):
    """I18N_DISABLED=1 → 503."""
    with patch("src.api.users.settings") as mock_settings:
        mock_settings.i18n_disabled = True
        mock_settings.app_base_url = ""
        mock_settings.supported_locales = "en,ko,ja"
        res = client.post(
            "/api/users/me/preferred-language",
            json={"language": "ko"},
        )
        assert res.status_code == 503
        assert "i18n feature is disabled" in res.json()["detail"]
