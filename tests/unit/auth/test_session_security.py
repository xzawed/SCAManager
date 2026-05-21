"""세션 변조(Session Tampering) 방어 단위 테스트.
Unit tests for session tampering defense in get_current_user() and require_login().

src/auth/session.py 의 비정상 user_id 값 처리 및 존재하지 않는 사용자 리다이렉트 검증.
Verifies handling of malformed user_id values and redirect for nonexistent users.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-cid")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-csecret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

from src.auth.session import get_current_user, require_login


def _req(session_data=None):
    """session dict을 가진 MagicMock Request를 반환한다.
    Returns a MagicMock Request with the given session dict.
    """
    req = MagicMock()
    req.session = session_data if session_data is not None else {}
    return req


def _mock_db_not_found():
    """DB에 사용자가 없는 상황을 모의하는 mock DB 컨텍스트를 반환한다.
    Returns a mock DB context that simulates a user not found in the database.
    """
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    return mock_db


def test_get_current_user_with_string_user_id_returns_none():
    """세션 user_id가 문자열("admin")이면 None을 반환해야 한다.
    When session user_id is a string like "admin", get_current_user must return None.

    이유: "admin"은 truthy이므로 DB 조회로 진입하나 DB에는 해당 사용자가 없어야 함.
    Reason: "admin" is truthy so it enters the DB lookup, but must find nothing.
    """
    mock_db = _mock_db_not_found()
    with patch("src.auth.session.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__.return_value = mock_db
        result = get_current_user(_req({"user_id": "admin"}))
    assert result is None


def test_get_current_user_with_negative_user_id_returns_none():
    """세션 user_id가 음수(-1)이면 None을 반환해야 한다.
    When session user_id is -1 (invalid negative ID), get_current_user must return None.

    이유: -1은 truthy이므로 DB 조회로 진입하나 유효한 PK가 없어 None 반환.
    Reason: -1 is truthy so it enters the DB lookup, but no valid PK exists.
    """
    mock_db = _mock_db_not_found()
    with patch("src.auth.session.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__.return_value = mock_db
        result = get_current_user(_req({"user_id": -1}))
    assert result is None


def test_get_current_user_with_zero_user_id_returns_none():
    """세션 user_id가 0이면 None을 반환해야 한다.
    When session user_id is 0 (falsy value), get_current_user must return None immediately.

    이유: 0은 Python에서 falsy이므로 `if not user_id` 분기에서 즉시 None 반환.
    Reason: 0 is falsy in Python, so the `if not user_id` guard returns None immediately.
    """
    # user_id=0은 falsy이므로 SessionLocal을 호출하지 않아야 함
    # user_id=0 is falsy so SessionLocal must not be called at all
    result = get_current_user(_req({"user_id": 0}))
    assert result is None


def test_require_login_with_nonexistent_user_raises_redirect():
    """DB에 존재하지 않는 user_id로 require_login 호출 시 /auth/github 302 리다이렉트 발생 (사이클 117).
    When require_login is called with a valid-looking but nonexistent user_id,
    it must raise HTTPException with status 302 and Location: /auth/github (cycle 117).

    이유: get_current_user가 None을 반환하면 require_login이 /auth/github 302 리다이렉트를 발생시킴.
    Reason: when get_current_user returns None, require_login raises 302 to /auth/github.
    """
    mock_db = _mock_db_not_found()
    with patch("src.auth.session.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__.return_value = mock_db
        with pytest.raises(HTTPException) as exc_info:
            require_login(_req({"user_id": 99999}))

    assert exc_info.value.status_code == 302
    assert exc_info.value.headers["Location"] == "/auth/github"
