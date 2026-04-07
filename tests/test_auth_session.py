import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-cid")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-csecret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from src.auth.session import get_current_user, require_login
from src.models.user import User


def _req(session_data=None):
    """session dict을 가진 MagicMock Request 반환."""
    req = MagicMock()
    req.session = session_data if session_data is not None else {}
    return req


def test_get_current_user_no_session():
    """세션에 user_id 없으면 None 반환."""
    result = get_current_user(_req({}))
    assert result is None


def test_get_current_user_invalid_id():
    """세션에 user_id 있지만 DB에 없으면 None 반환."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.auth.session.SessionLocal", return_value=mock_db):
        result = get_current_user(_req({"user_id": 999}))
    assert result is None


def test_get_current_user_valid():
    """세션에 user_id 있고 DB에 유저 존재하면 User 반환."""
    mock_user = User(id=1, github_id="g1", email="a@b.com", display_name="Test")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    with patch("src.auth.session.SessionLocal", return_value=mock_db):
        result = get_current_user(_req({"user_id": 1}))
    assert result is mock_user


def test_require_login_no_session_raises_302():
    """비로그인 시 HTTPException 302 with Location: /login."""
    with pytest.raises(HTTPException) as exc_info:
        require_login(_req({}))
    assert exc_info.value.status_code == 302
    assert exc_info.value.headers["Location"] == "/login"


def test_require_login_returns_user():
    """로그인 상태에서 User 반환."""
    mock_user = User(id=1, github_id="g1", email="a@b.com", display_name="Test")
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user
    with patch("src.auth.session.SessionLocal", return_value=mock_db):
        result = require_login(_req({"user_id": 1}))
    assert result is mock_user
