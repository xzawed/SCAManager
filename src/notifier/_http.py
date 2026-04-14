"""SSRF-safe HTTP helpers for external webhook notifiers."""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = {"https"}
_TIMEOUT = 10.0


def _is_dangerous_ip(addr: str) -> bool:
    """Return True if the IP address should be blocked (private/loopback/link-local/etc.)."""
    try:
        ip = ipaddress.ip_address(addr)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        return False


def validate_external_url(url: str) -> bool:
    """Return True only if *url* is safe to use as an external webhook target.

    Blocks:
    - Non-https schemes (http, ftp, file, …)
    - IP literals in private/loopback/link-local/reserved/multicast ranges
    - Hostnames that DNS-resolve to any such address (DNS-rebinding defence)
    - Empty or malformed URLs
    """
    if not url:
        return False

    parsed = urlparse(url)
    hostname = parsed.hostname

    if parsed.scheme not in _ALLOWED_SCHEMES:
        logger.warning("SSRF guard: rejected non-https scheme '%s' in URL: %s", parsed.scheme, url)
        return False

    if not hostname:
        return False

    # Direct IP literal — check immediately without DNS lookup
    try:
        ipaddress.ip_address(hostname)
        is_bad = _is_dangerous_ip(hostname)
        if is_bad:
            logger.warning("SSRF guard: rejected private/loopback IP literal '%s'", hostname)
        return not is_bad
    except ValueError:
        pass  # hostname is a domain name — proceed to DNS resolution

    # DNS resolution: block if any returned address is private/internal
    try:
        addrs = [sockaddr[0] for _f, _t, _p, _c, sockaddr in socket.getaddrinfo(hostname, None)]
    except socket.gaierror:
        logger.warning("SSRF guard: DNS resolution failed for hostname '%s'", hostname)
        return False

    bad_addr = next((a for a in addrs if _is_dangerous_ip(a)), None)
    if bad_addr:
        logger.warning(
            "SSRF guard: hostname '%s' resolved to blocked IP '%s'", hostname, bad_addr
        )
    return bad_addr is None


def build_safe_client() -> httpx.AsyncClient:
    """Return an httpx.AsyncClient configured for safe external webhook calls.

    - timeout=10 seconds for all operations
    - follow_redirects=False to prevent redirect-based SSRF
    """
    return httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False)
