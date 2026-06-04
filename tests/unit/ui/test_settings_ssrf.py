"""src/ui/routes/settings.py::_is_safe_webhook_url SSRF 폼 검증 단위 테스트.
Unit tests for the settings form SSRF validator (_is_safe_webhook_url).

WBS 감사 P2 — 발신 가드(_http.py)와의 검증 일관성 회귀 가드:
https-only + CGNAT(100.64.0.0/10) 차단 + 위험 IP/호스트 차단.
WBS audit P2 — regression guard for consistency with the outbound guard:
https-only + CGNAT block + dangerous IP/host block.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest

from src.ui.routes.settings import _is_safe_webhook_url


def test_none_and_empty_allowed():
    # 미설정(None/빈문자열) webhook 은 허용 — 선택 필드
    # Unset (None/empty) webhook is allowed — optional field
    assert _is_safe_webhook_url(None) is True
    assert _is_safe_webhook_url("") is True


def test_https_public_domain_allowed():
    assert _is_safe_webhook_url("https://hooks.example.com/abc") is True


@pytest.mark.parametrize(
    "url",
    [
        "http://hooks.example.com/abc",   # https-only — http 거부 (발신 가드 일관)
        "ftp://example.com/x",            # 비-https 스킴
        "file:///etc/passwd",             # file 스킴
    ],
)
def test_non_https_scheme_rejected(url):
    assert _is_safe_webhook_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://10.0.0.1/hook",          # private
        "https://127.0.0.1/hook",         # loopback
        "https://169.254.169.254/hook",   # link-local (cloud metadata)
        "https://100.64.1.1/hook",        # CGNAT (RFC 6598) — 핵심 회귀 가드 / key regression guard
    ],
)
def test_dangerous_ip_literals_rejected(url):
    assert _is_safe_webhook_url(url) is False


@pytest.mark.parametrize(
    "url",
    [
        "https://localhost/hook",
        "https://metadata.google.internal/x",
    ],
)
def test_blocked_hosts_rejected(url):
    assert _is_safe_webhook_url(url) is False
