"""src/shared/ssrf.py 단위 테스트 — is_dangerous_ip 단일 출처 IP 분류.
Unit tests for src/shared/ssrf.py — is_dangerous_ip single-source IP classification.
"""
import pytest

from src.shared.ssrf import is_dangerous_ip


@pytest.mark.parametrize(
    "addr",
    [
        "10.0.0.1",            # private
        "192.168.1.1",         # private
        "172.16.0.1",          # private
        "127.0.0.1",           # loopback
        "169.254.169.254",     # link-local (cloud metadata)
        "0.0.0.0",             # reserved
        "224.0.0.1",           # multicast
        "100.64.1.1",          # CGNAT (RFC 6598) — 핵심 회귀 가드 / key regression guard
        "100.127.255.255",     # CGNAT 상단 경계 / CGNAT upper boundary
        "::1",                 # IPv6 loopback
        "fe80::1",             # IPv6 link-local
    ],
)
def test_dangerous_ips_blocked(addr):
    assert is_dangerous_ip(addr) is True


@pytest.mark.parametrize(
    "addr",
    [
        "8.8.8.8",             # public
        "1.1.1.1",             # public
        "100.63.255.255",      # CGNAT 직전 (공인) / just below CGNAT (public)
        "100.128.0.0",         # CGNAT 직후 (공인) / just above CGNAT (public)
    ],
)
def test_public_ips_allowed(addr):
    assert is_dangerous_ip(addr) is False


def test_domain_name_returns_false():
    # 도메인명은 IP 파싱 실패 → False (DNS 해석은 호출자 책임)
    # Domain names fail IP parsing → False (DNS resolution is the caller's responsibility)
    assert is_dangerous_ip("example.com") is False
    assert is_dangerous_ip("") is False


def test_cgnat_check_no_version_error_for_ipv6():
    # IPv6 주소가 IPv4 CGNAT 네트워크와 비교돼도 TypeError 없이 동작 (다른 사유로 차단/허용)
    # IPv6 vs IPv4-CGNAT comparison must not raise TypeError (blocked/allowed by other rules)
    assert is_dangerous_ip("2001:4860:4860::8888") is False  # public IPv6 (Google DNS)
