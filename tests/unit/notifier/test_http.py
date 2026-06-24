import os

# src 임포트 전 환경변수 주입 필수
# Environment variables must be injected before src imports.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

import logging
import socket
from unittest.mock import patch

import httpx

from src.notifier._http import validate_external_url, build_safe_client


# ---------------------------------------------------------------------------
# validate_external_url 테스트
# ---------------------------------------------------------------------------


async def test_validate_blocks_loopback_ipv4():
    # 127.0.0.1 루프백 주소는 반드시 차단
    # 127.0.0.1 loopback address must be blocked.
    assert await validate_external_url("http://127.0.0.1/hook") is False


async def test_validate_blocks_loopback_ipv6():
    # IPv6 루프백 ::1 도 차단
    # IPv6 loopback ::1 must also be blocked.
    assert await validate_external_url("http://[::1]/hook") is False


async def test_validate_blocks_private_10_range():
    # RFC 1918 10.x.x.x 사설 대역 차단
    # RFC 1918 10.x.x.x private range must be blocked.
    assert await validate_external_url("https://10.0.0.1/hook") is False


async def test_validate_blocks_private_192_range():
    # RFC 1918 192.168.x.x 사설 대역 차단
    # RFC 1918 192.168.x.x private range must be blocked.
    assert await validate_external_url("https://192.168.1.1/hook") is False


async def test_validate_blocks_link_local():
    # AWS IMDSv1 인스턴스 메타데이터 주소 차단 (169.254.169.254)
    assert await validate_external_url("https://169.254.169.254/hook") is False


async def test_validate_blocks_http_scheme():
    # https 전용 — http:// 스킴은 차단
    assert await validate_external_url("http://example.com/hook") is False


async def test_validate_allows_https_public_url():
    # 공인 IP로 해석되는 https URL은 허용
    # socket.getaddrinfo를 mock해 공인 IP(1.2.3.4) 반환
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("1.2.3.4", 0))]
    with patch("socket.getaddrinfo", return_value=fake_addrinfo):
        assert await validate_external_url("https://discord.com/api/webhooks/123") is True


async def test_validate_hostname_resolves_to_private_ip_blocked():
    # DNS가 사설 IP를 반환하는 외부처럼 보이는 도메인 차단 (DNS 리바인딩 방어)
    # Block seemingly external domains whose DNS resolves to private IPs (DNS rebinding defence).
    fake_addrinfo = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("10.0.0.1", 0))]
    with patch("socket.getaddrinfo", return_value=fake_addrinfo):
        assert await validate_external_url("https://evil.example.com/hook") is False


async def test_validate_empty_string_returns_false():
    # 빈 문자열은 False 반환
    assert await validate_external_url("") is False


async def test_validate_invalid_url_returns_false():
    # URL 형식이 아닌 문자열은 False 반환
    assert await validate_external_url("not-a-url") is False


async def test_validate_https_without_host_blocked():
    # https 스킴이지만 host 가 없는 URL 은 fail-closed 차단 (_http.py:54-55)
    # https scheme but no host → fail-closed block. 기존 "not-a-url" 은 scheme 단계(L50)에서
    # 막혀 이 분기에 미도달했음 — fail-open 회귀(L55를 return True 로) 봉인.
    assert await validate_external_url("https:///path-only") is False


async def test_validate_dns_resolution_failure_blocked():
    # 도메인이 DNS 해석에 실패하면 fail-closed 차단 (_http.py:73-75, socket.gaierror)
    # DNS resolution failure → fail-closed block. 기존 DNS 테스트는 getaddrinfo 성공 mock 만
    # 사용해 except 분기에 미도달했음 — asyncio.to_thread 경유로도 gaierror 가 surface 됨.
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("name resolution failed")):
        assert await validate_external_url("https://nonexistent.invalid/hook") is False


async def test_validate_dns_timeout_blocked():
    # DNS 조회가 timeout 되어도 fail-closed 차단 (사이클 159 — 158 회고 P2)
    # socket.timeout(=TimeoutError) 은 gaierror 형제 예외 — 기존 except gaierror 는 미포착해
    # notify 태스크로 전파됐음. except OSError 확장으로 graceful 차단.
    # DNS timeout → fail-closed block; socket.timeout was previously uncaught and crashed the task.
    with patch("socket.getaddrinfo", side_effect=socket.timeout("timed out")):
        assert await validate_external_url("https://slow.example.com/hook") is False


async def test_validate_dns_oserror_blocked():
    # 일반 OSError(예: 네트워크 도달 불가) 도 fail-closed 차단 — except OSError 포섭 (158 회고 P2)
    # General OSError (e.g. network unreachable) → fail-closed block via the widened except OSError.
    with patch("socket.getaddrinfo", side_effect=OSError("network is unreachable")):
        assert await validate_external_url("https://unreachable.example.com/hook") is False


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
    # Must not follow redirects (SSRF defence).
    client = build_safe_client()
    assert client.follow_redirects is False


# ---------------------------------------------------------------------------
# 경고 로그 테스트
# Warning log tests.
# ---------------------------------------------------------------------------


async def test_validate_logs_warning_on_private_ip(caplog):
    # 사설 IP 차단 시 logger.warning이 호출되어야 한다
    with caplog.at_level(logging.WARNING, logger="src.notifier._http"):
        result = await validate_external_url("https://192.168.1.1/hook")
    assert result is False
    assert len(caplog.records) >= 1
    assert any(r.levelno == logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# #12 — SSRF docstring 정직화 회귀 가드 (DNS-rebinding 과대표현 재발 차단)
# DNS-rebinding overclaim regression guard.
# ---------------------------------------------------------------------------


def test_validate_docstring_no_dns_rebinding_overclaim():
    """#12: validate_external_url docstring 이 'DNS-rebinding defence' 를 방어 단언으로 과대표현하지
    않고, validate 시점 한계(connect 재해석 TOCTOU)를 명시해야 한다 — 정직화 봉인."""
    doc = validate_external_url.__doc__ or ""
    assert "NOT a full DNS-rebinding defence" in doc  # 정직한 한계 명시
    assert "validate-time" in doc
    assert "connect time" in doc
    assert "TOCTOU" in doc


def test_build_safe_client_docstring_notes_toctou_limitation():
    """#12: build_safe_client docstring 이 connect-time 재해석 TOCTOU 한계를 명시해야 한다."""
    doc = build_safe_client.__doc__ or ""
    assert "TOCTOU" in doc
    assert "connect time" in doc
