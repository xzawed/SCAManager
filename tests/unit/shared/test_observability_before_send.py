"""observability._before_send PII 스크러빙 회귀 가드 (Cycle 80 PR 1).

5+1 cross-verify P0-1 처리 — 신규 헤더 5건 추가 + URL fragment 제거 추가.

검증 영역:
- URL query string + fragment 제거
- 민감 헤더 10건 (authorization / x-api-key / x-hub-signature[/-256] /
  x-github-token / x-telegram-bot-api-secret-token / x-webhook-token /
  x-forwarded-for / x-real-ip / cookie)
- Cookies + body data scrubbing
- 정상 헤더 (Content-Type 등) 통과 검증
"""
from __future__ import annotations

import os

# conftest.py 가 실행되기 전에 필수 env var 주입
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest

# `_before_send` 함수 = sentry-sdk 의존 X (단순 dict 변환) — devcontainer 도 직접 검증 가능
# `_before_send` is sentry-sdk independent (pure dict transform) — runs everywhere
from src.shared import observability  # noqa: E402


# ─── URL query/fragment 제거 ────────────────────────────────────────


class TestUrlScrub:
    def test_query_string_removed(self):
        event = {"request": {"url": "https://app/auth/callback?token=secret&state=xyz"}}
        result = observability._before_send(event, {})
        assert result["request"]["url"] == "https://app/auth/callback"

    def test_fragment_removed(self):
        event = {"request": {"url": "https://app/dashboard#token=abc"}}
        result = observability._before_send(event, {})
        assert result["request"]["url"] == "https://app/dashboard"

    def test_query_and_fragment_removed(self):
        event = {"request": {"url": "https://app/r?a=1#b=2"}}
        result = observability._before_send(event, {})
        assert result["request"]["url"] == "https://app/r"

    def test_clean_url_unchanged(self):
        event = {"request": {"url": "https://app/health"}}
        result = observability._before_send(event, {})
        assert result["request"]["url"] == "https://app/health"

    def test_no_url_field_no_crash(self):
        event = {"request": {}}
        result = observability._before_send(event, {})
        assert "url" not in result["request"]


# ─── 민감 헤더 10건 스크러빙 ────────────────────────────────────────


class TestHeaderScrub:
    @pytest.mark.parametrize("header_name", [
        "Authorization",
        "X-API-Key",
        "X-Hub-Signature",
        "X-Hub-Signature-256",
        "X-GitHub-Token",
        "X-Telegram-Bot-Api-Secret-Token",
        "X-Webhook-Token",
        "X-Forwarded-For",
        "X-Real-IP",
        "Cookie",
    ])
    def test_sensitive_headers_filtered(self, header_name):
        event = {"request": {"headers": {header_name: "secret-value-12345"}}}
        result = observability._before_send(event, {})
        assert result["request"]["headers"][header_name] == "[Filtered]"

    def test_lowercase_header_filtered(self):
        """대소문자 무관 검증."""
        event = {"request": {"headers": {"authorization": "Bearer xyz"}}}
        result = observability._before_send(event, {})
        assert result["request"]["headers"]["authorization"] == "[Filtered]"

    def test_clean_headers_pass_through(self):
        """정상 헤더 (Content-Type 등) 통과 검증."""
        event = {"request": {"headers": {
            "Content-Type": "application/json",
            "User-Agent": "pytest",
        }}}
        result = observability._before_send(event, {})
        assert result["request"]["headers"]["Content-Type"] == "application/json"
        assert result["request"]["headers"]["User-Agent"] == "pytest"

    def test_mixed_headers_only_sensitive_filtered(self):
        """민감 + 정상 혼재 = 민감 만 filter."""
        event = {"request": {"headers": {
            "Authorization": "Bearer xyz",
            "Content-Type": "application/json",
            "X-Real-IP": "1.2.3.4",
        }}}
        result = observability._before_send(event, {})
        assert result["request"]["headers"]["Authorization"] == "[Filtered]"
        assert result["request"]["headers"]["X-Real-IP"] == "[Filtered]"
        assert result["request"]["headers"]["Content-Type"] == "application/json"


# ─── Cookies + body data 스크러빙 ────────────────────────────────────


class TestCookieAndBodyScrub:
    def test_cookies_cleared(self):
        event = {"request": {"cookies": {"session": "secret-cookie", "csrf": "xyz"}}}
        result = observability._before_send(event, {})
        assert result["request"]["cookies"] == {}

    def test_body_data_filtered(self):
        event = {"request": {"data": {"username": "alice", "password": "secret"}}}
        result = observability._before_send(event, {})
        assert result["request"]["data"] == "[Filtered]"

    def test_no_cookies_no_data_no_crash(self):
        event = {"request": {"url": "https://app/health"}}
        result = observability._before_send(event, {})
        assert result is event


# ─── 헤더 화이트리스트 상수 검증 ────────────────────────────────────


class TestSensitiveHeadersConstant:
    def test_all_lowercase(self):
        """모든 헤더 이름 lowercase 의무 (대소문자 비교 안전)."""
        for header in observability._SENSITIVE_HEADERS:
            assert header == header.lower(), f"{header!r} 가 lowercase 가 아님"

    def test_includes_10_headers(self):
        """Cycle 80 PR 1 — 10 헤더 모두 포함."""
        expected = {
            "authorization",
            "x-api-key",
            "x-hub-signature",
            "x-hub-signature-256",
            "x-github-token",
            "x-telegram-bot-api-secret-token",
            "x-webhook-token",
            "x-forwarded-for",
            "x-real-ip",
            "cookie",
        }
        assert observability._SENSITIVE_HEADERS == expected
