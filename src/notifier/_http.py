"""SSRF-safe HTTP helpers for external webhook notifiers."""
import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

from src.constants import HTTP_CLIENT_TIMEOUT
from src.shared.ssrf import is_dangerous_ip

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"https"}


def url_host_for_log(url):
    """로그용 URL 라벨 — **host 만** 남기고 경로·쿼리를 버린다.
    Log-safe URL label: keeps only the host, dropping path and query.

    🔴 왜 필요한가 (2026-07-19 2차 회고 P1): Slack(`hooks.slack.com/services/<SECRET>`)·
    Discord(`discord.com/api/webhooks/<id>/<TOKEN>`) webhook 은 **URL 자체가 credential** 이다.
    경로만 알면 누구나 그 채널로 발신할 수 있으므로, URL 전문을 로그에 남기면 시크릿 유출이다.
    호스트는 남겨 어느 채널이 막혔는지는 운영자가 판독할 수 있게 한다.
    Slack/Discord webhook URLs *are* the credential — the path is the secret. Keep the host so
    operators can still tell which channel was blocked.

    🔴 이 헬퍼를 우회해 `webhook_url` 을 직접 로깅하지 말 것 (호출처 6곳 전부 경유).
    """
    try:
        return urlparse(url).netloc or "(no-host)"
    except ValueError:
        return "(unparseable)"


async def validate_external_url(url: str) -> bool:
    """Return True only if *url* is safe to use as an external webhook target.

    Blocks:
    - Non-https schemes (http, ftp, file, …)
    - IP literals in private/loopback/link-local/reserved/multicast ranges
    - Hostnames whose DNS *currently* resolves to such an address
    - Empty or malformed URLs

    🔴 한계 (정직화 — Task9 P2 #12): 이것은 validate 시점 1차 차단일 뿐 **완전한 DNS-rebinding
    방어가 아니다**. httpx 는 connect 시점에 호스트명을 독립적으로 재해석하므로(이 함수의 getaddrinfo
    와 별개), validate→connect 사이 DNS 가 내부 IP 로 rebind 되면 우회 가능한 TOCTOU 가 잔존한다.
    완전 방어는 connect 시 검증된 IP 핀이 필요하나 httpx 가 native 미지원이라 미적용.
    🔴 Limitation (Task9 P2 #12): only a validate-time first block, NOT a full DNS-rebinding defence.
    httpx re-resolves the hostname independently at connect time, so a TOCTOU remains if DNS rebinds
    to an internal IP between validate and connect. A full fix needs a connect-time pinned IP, which
    httpx does not natively support.

    DNS 조회는 asyncio.to_thread 으로 실행 — 이벤트 루프 블로킹 방지.
    DNS lookup runs in asyncio.to_thread to avoid blocking the event loop.
    """
    if not url:
        return False

    parsed = urlparse(url)
    hostname = parsed.hostname

    if parsed.scheme not in _ALLOWED_SCHEMES:
        logger.warning(
            "SSRF guard: rejected non-https scheme '%s' in URL: %s",
            parsed.scheme,
            url_host_for_log(url),
        )
        return False

    if not hostname:
        return False

    # Direct IP literal — check immediately without DNS lookup
    try:
        ipaddress.ip_address(hostname)
        is_bad = is_dangerous_ip(hostname)
        if is_bad:
            logger.warning("SSRF guard: rejected private/loopback IP literal '%s'", hostname)
        return not is_bad
    except ValueError:
        pass  # hostname is a domain name — proceed to DNS resolution

    # DNS resolution: block if any returned address is private/internal.
    # socket.getaddrinfo 는 sync blocking — asyncio.to_thread 로 오프로드.
    # socket.getaddrinfo is sync blocking — offload via asyncio.to_thread.
    try:
        raw = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
        addrs = [sockaddr[0] for _f, _t, _p, _c, sockaddr in raw]
    except OSError as exc:
        # gaierror(이름 해석 실패) 외에 socket.timeout·일반 OSError(네트워크 실패) 도 fail-closed.
        # 이 분기가 gaierror 만 잡으면 DNS timeout/OSError 가 notify 태스크로 전파돼 크래시
        # (사이클 159 — 158 회고 P2). gaierror·timeout 모두 OSError 서브클래스라 한 번에 포섭.
        # Catch gaierror plus socket.timeout / general OSError — all fail closed, never crash.
        logger.warning(
            "SSRF guard: DNS resolution failed for hostname '%s' (%s)", hostname, type(exc).__name__
        )
        return False

    bad_addr = next((a for a in addrs if is_dangerous_ip(a)), None)
    if bad_addr:
        logger.warning(
            "SSRF guard: hostname '%s' resolved to blocked IP '%s'", hostname, bad_addr
        )
    return bad_addr is None


def build_safe_client() -> httpx.AsyncClient:
    """Return an httpx.AsyncClient configured for safe external webhook calls.

    - timeout=10 seconds for all operations
    - follow_redirects=False to prevent redirect-based SSRF

    🔴 한계 (Task9 P2 #12): 목적지 호스트는 connect 시 httpx 가 재해석하므로 validate_external_url
    의 1차 IP 차단 이후의 DNS-rebinding TOCTOU 를 막지 못한다(검증된 IP 핀 미적용). 외부 webhook 은
    재시도 금지 채널이고 follow_redirects=False 라 잔여 위험은 제한적.
    🔴 Limitation (Task9 P2 #12): httpx re-resolves the destination host at connect time, so this does
    NOT close the DNS-rebinding TOCTOU after validate_external_url's first block (no pinned IP).
    External webhooks are non-retried and follow_redirects=False, so residual risk is limited.
    """
    return httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT, follow_redirects=False)
