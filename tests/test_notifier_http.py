import os

# src 임포트 전 환경변수 주입 필수
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

import logging
import socket
from unittest.mock import patch, MagicMock

import httpx
import pytest

from src.notifier._http import validate_external_url, build_safe_client


# ---------------------------------------------------------------------------
# validate_external_url 테스트
# ---------------------------------------------------------------------------


def test_validate_blocks_loopback_ipv4():
    # 127.0.0.1 루프백 주소는 반드시 차단
    assert validate_external_url("http://127.0.0.1/hook") is False


def test_validate_blocks_loopback_ipv6():
    # IPv6 루프백 ::1 도 차단
    assert validate_external_url("http://[::1]/hook") is False


def test_validate_blocks_private_10_range():
    # RFC 1918 10.x.x.x 사설 대역 차단
    assert validate_external_url("https://10.0.0.1/hook") is False


def test_validate_blocks_private_192_range():
    # RFC 1918 192.168.x.x 사설 대역 차단
    assert validate_external_url("https://192.168.1.1/hook") is False


def test_validate_blocks_link_local():
    # AWS IMDSv1 인스턴스 메타데이터 주소 차단 (169.254.169.254)
    assert validate_external_url("https://169.254.169.254/hook") is False


def test_validate_blocks_http_scheme():
    # https 전용 — http:// 스킴은 차단
    assert validate_external_url("http://example.com/hook") is False


def test_validate_allows_https_public_url():
    # 공인 IP로 해석되는 https URL은 허용
    # socket.getaddrinfo를 mock해 공인 IP(1.2.3.4) 반환
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("1.2.3.4", 0))]
    with patch("socket.getaddrinfo", return_value=fake_addrinfo):
        assert validate_external_url("https://discord.com/api/webhooks/123") is True


def test_validate_hostname_resolves_to_private_ip_blocked():
    # DNS가 사설 IP를 반환하는 외부처럼 보이는 도메인 차단 (DNS 리바인딩 방어)
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))]
    with patch("socket.getaddrinfo", return_value=fake_addrinfo):
        assert validate_external_url("https://evil.example.com/hook") is False


def test_validate_empty_string_returns_false():
    # 빈 문자열은 False 반환
    assert validate_external_url("") is False


def test_validate_invalid_url_returns_false():
    # URL 형식이 아닌 문자열은 False 반환
    assert validate_external_url("not-a-url") is False


# ---------------------------------------------------------------------------
# build_safe_client 테스트
# ---------------------------------------------------------------------------


def test_build_safe_client_returns_async_client():
    # 반환값이 httpx.AsyncClient 인스턴스여야 한다
    client = build_safe_client()
    assert isinstance(client, httpx.AsyncClient)


def test_build_safe_client_timeout():
    # connect 및 read timeout이 모두 10초 이하여야 한다
    client = build_safe_client()
    timeout = client.timeout
    assert timeout.connect is not None and timeout.connect <= 10.0
    assert timeout.read is not None and timeout.read <= 10.0


def test_build_safe_client_no_follow_redirects():
    # 리다이렉트를 따라가지 않아야 한다 (SSRF 방어)
    client = build_safe_client()
    assert client.follow_redirects is False


# ---------------------------------------------------------------------------
# 경고 로그 테스트
# ---------------------------------------------------------------------------


def test_validate_logs_warning_on_private_ip(caplog):
    # 사설 IP 차단 시 logger.warning이 호출되어야 한다
    with caplog.at_level(logging.WARNING, logger="src.notifier._http"):
        result = validate_external_url("https://192.168.1.1/hook")
    assert result is False
    assert len(caplog.records) >= 1
    assert any(r.levelno == logging.WARNING for r in caplog.records)
