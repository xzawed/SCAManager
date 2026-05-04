"""Cycle 79 PR 2 — require_admin Depends + admin allow-list 회귀 가드.

3 layer 검증:
- kill-switch (`SAAS_MULTITENANT_DISABLED=1`) → 503
- require_login → 302 (비로그인)
- admin email allow-list → 403 (admin 부재) 또는 503 (allow-list 미설정)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.auth.session import (
    CurrentUser,
    _parse_admin_emails,
    require_admin,
)


# ─── _parse_admin_emails ──────────────────────────────────────────────


class TestParseAdminEmails:
    def test_empty_returns_empty_set(self):
        assert _parse_admin_emails("") == set()

    def test_single_email(self):
        assert _parse_admin_emails("alice@example.com") == {"alice@example.com"}

    def test_csv_strips_whitespace(self):
        result = _parse_admin_emails("  alice@example.com , bob@example.com  ")
        assert result == {"alice@example.com", "bob@example.com"}

    def test_lowercase_normalized(self):
        result = _parse_admin_emails("Alice@Example.COM, BOB@example.com")
        assert result == {"alice@example.com", "bob@example.com"}

    def test_skips_blank_entries(self):
        result = _parse_admin_emails("alice@example.com,,,bob@example.com,")
        assert result == {"alice@example.com", "bob@example.com"}


# ─── require_admin (kill-switch layer) ──────────────────────────────


def _make_request_with_user(user_id: int = 1) -> MagicMock:
    """세션 사용자 mock — request.session.get('user_id') 응답."""
    req = MagicMock()
    req.session.get.return_value = user_id
    return req


def _make_user(email: str = "alice@example.com") -> CurrentUser:
    return CurrentUser(
        id=1,
        github_login="alice",
        email=email,
        display_name="Alice",
        plaintext_token="ghp_test",
    )


def test_require_admin_kill_switch_returns_503(monkeypatch):
    """kill-switch 활성 시 503 반환 (Layer 1)."""
    monkeypatch.setenv("SAAS_MULTITENANT_DISABLED", "1")
    req = _make_request_with_user()
    with pytest.raises(HTTPException) as exc_info:
        require_admin(req)
    assert exc_info.value.status_code == 503
    assert "disabled" in exc_info.value.detail.lower()


def test_require_admin_not_logged_in_redirects(monkeypatch):
    """비로그인 시 302 redirect (Layer 2 — require_login 위임)."""
    monkeypatch.delenv("SAAS_MULTITENANT_DISABLED", raising=False)
    monkeypatch.setattr("src.config.settings.saas_admin_emails", "alice@example.com")
    req = MagicMock()
    req.session.get.return_value = None  # 비로그인
    with pytest.raises(HTTPException) as exc_info:
        require_admin(req)
    assert exc_info.value.status_code == 302


def test_require_admin_allowlist_unset_returns_503(monkeypatch):
    """allow-list 미설정 시 503 (silent open access 회피 — Layer 3a)."""
    monkeypatch.delenv("SAAS_MULTITENANT_DISABLED", raising=False)
    monkeypatch.setattr("src.config.settings.saas_admin_emails", "")
    req = _make_request_with_user()
    user = _make_user()
    with patch("src.auth.session.require_login", return_value=user):
        with pytest.raises(HTTPException) as exc_info:
            require_admin(req)
    assert exc_info.value.status_code == 503
    assert "unset" in exc_info.value.detail.lower()


def test_require_admin_user_not_in_allowlist_returns_403(monkeypatch):
    """admin allow-list 부재 시 403 (Layer 3b)."""
    monkeypatch.delenv("SAAS_MULTITENANT_DISABLED", raising=False)
    monkeypatch.setattr("src.config.settings.saas_admin_emails", "admin@example.com")
    req = _make_request_with_user()
    user = _make_user(email="alice@example.com")  # admin allow-list 외
    with patch("src.auth.session.require_login", return_value=user):
        with pytest.raises(HTTPException) as exc_info:
            require_admin(req)
    assert exc_info.value.status_code == 403


def test_require_admin_user_in_allowlist_returns_user(monkeypatch):
    """allow-list 명시 사용자 = 정상 반환."""
    monkeypatch.delenv("SAAS_MULTITENANT_DISABLED", raising=False)
    monkeypatch.setattr("src.config.settings.saas_admin_emails", "alice@example.com,bob@example.com")
    req = _make_request_with_user()
    user = _make_user(email="alice@example.com")
    with patch("src.auth.session.require_login", return_value=user):
        result = require_admin(req)
    assert result is user
    assert result.email == "alice@example.com"


def test_require_admin_email_case_insensitive(monkeypatch):
    """email 대소문자 무관 — Alice@Example.COM matches alice@example.com allow-list."""
    monkeypatch.delenv("SAAS_MULTITENANT_DISABLED", raising=False)
    monkeypatch.setattr("src.config.settings.saas_admin_emails", "Alice@Example.COM")
    req = _make_request_with_user()
    user = _make_user(email="alice@example.com")
    with patch("src.auth.session.require_login", return_value=user):
        result = require_admin(req)
    assert result is user
