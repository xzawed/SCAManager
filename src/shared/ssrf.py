"""SSRF 방어 IP 분류 — 발신 가드(_http.py)와 폼 검증(settings.py) 단일 출처.
SSRF-defense IP classification — single source for the outbound guard (_http.py)
and the settings form validator (settings.py).

두 검증기가 각자 IP 위험 판정을 중복 구현하면 한쪽만 갱신돼 drift(예: CGNAT 누락)가
발생한다 — 본 모듈로 단일화해 회귀를 차단한다 (WBS 감사 P2 — 검증 일관성).
Duplicating the IP-danger check in two validators causes drift (e.g. a missing CGNAT
range) when only one is updated — this module unifies it (WBS audit P2 — validation consistency).
"""
import ipaddress
from urllib.parse import urlparse

# CGNAT(Carrier-Grade NAT) 대역 — RFC 6598. ip.is_private/is_reserved 어디에도 안 잡혀 명시 차단.
# CGNAT (Carrier-Grade NAT) range — RFC 6598. Not covered by is_private/is_reserved, so block it explicitly.
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

# webhook URL 저장-시(storage-time) 차단 호스트 — IMDS/메타데이터/루프백 (이름 기반, IP 리터럴은 is_dangerous_ip).
# Storage-time blocked webhook hosts — IMDS/metadata/loopback (name-based; IP literals via is_dangerous_ip).
_BLOCKED_WEBHOOK_HOSTS = frozenset({
    "localhost", "127.0.0.1", "::1",  # NOSONAR python:S1313 — 의도된 SSRF 차단 blocklist
    "0.0.0.0",  # nosec B104  # NOSONAR python:S1313 — 의도된 SSRF 차단 blocklist
    "169.254.169.254",  # AWS/GCP IMDS  # NOSONAR python:S1313 — 의도된 SSRF 차단 blocklist
    "metadata.google.internal",  # GCP metadata
    "fd00::ec2",  # AWS IPv6 IMDS  # NOSONAR python:S1313 — 의도된 SSRF 차단 blocklist
})


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


def is_safe_webhook_url(url: str | None) -> bool:  # pylint: disable=too-many-return-statements
    """사용자 제공 webhook URL 의 저장-시(storage-time) SSRF 안전성 판정 — settings 폼 + REST API 공유.

    https-only(발신 가드 정책 일치) + 차단 호스트 + 위험 IP 리터럴 거부. 빈/None 은 안전(미설정).
    도메인명은 IP 가 아니라 통과 → send-time validate_external_url 가 DNS 해석 후 최종 차단.
    반환 7개는 SSRF 방어 경로별 명확한 실패 사유라 의도적.
    Storage-time SSRF safety check for user-supplied webhook URLs — shared by settings form + REST API.
    https-only + blocked hosts + dangerous IP literals. Empty/None is safe (unset). Domain names pass
    (not IPs) and are resolved+blocked at send time by validate_external_url.
    """
    if not url:
        return True
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if host in _BLOCKED_WEBHOOK_HOSTS:
            return False
        if is_dangerous_ip(host):
            return False
        return True
    except Exception:  # pylint: disable=broad-except
        return False
