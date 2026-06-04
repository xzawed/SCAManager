"""SSRF 방어 IP 분류 — 발신 가드(_http.py)와 폼 검증(settings.py) 단일 출처.
SSRF-defense IP classification — single source for the outbound guard (_http.py)
and the settings form validator (settings.py).

두 검증기가 각자 IP 위험 판정을 중복 구현하면 한쪽만 갱신돼 drift(예: CGNAT 누락)가
발생한다 — 본 모듈로 단일화해 회귀를 차단한다 (WBS 감사 P2 — 검증 일관성).
Duplicating the IP-danger check in two validators causes drift (e.g. a missing CGNAT
range) when only one is updated — this module unifies it (WBS audit P2 — validation consistency).
"""
import ipaddress

# CGNAT(Carrier-Grade NAT) 대역 — RFC 6598. ip.is_private/is_reserved 어디에도 안 잡혀 명시 차단.
# CGNAT (Carrier-Grade NAT) range — RFC 6598. Not covered by is_private/is_reserved, so block it explicitly.
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")


def is_dangerous_ip(addr: str) -> bool:
    """IP 문자열이 SSRF 차단 대상인지 판정한다.
    Return True if the IP string should be blocked for SSRF.

    차단 대역: 사설 / 루프백 / 링크-로컬 / 예약 / 멀티캐스트 / CGNAT(100.64.0.0/10).
    Blocked ranges: private / loopback / link-local / reserved / multicast / CGNAT (100.64.0.0/10).

    IP 리터럴이 아니면(도메인명) False 반환 — 호출자가 DNS 해석 후 각 주소로 재호출한다.
    Returns False for non-IP strings (domain names) — callers resolve DNS and re-check each address.
    """
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        # 도메인명 등 IP 가 아닌 입력 — 여기서 판정 불가 (DNS 해석은 호출자 책임)
        # Non-IP input (e.g. domain name) — cannot classify here (caller resolves DNS)
        return False
    # `ip in _CGNAT_NETWORK` 은 버전 불일치(IPv6) 시 False 반환 — 안전 (ipaddress __contains__ 규약)
    # `ip in _CGNAT_NETWORK` returns False on version mismatch (IPv6) — safe (ipaddress __contains__ contract)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip in _CGNAT_NETWORK
    )
