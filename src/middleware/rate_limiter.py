"""API Rate Limiting 미들웨어 설정.
API rate limiting middleware configuration using slowapi.
"""
import ipaddress
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

logger = logging.getLogger(__name__)

# Railway 엣지가 컨테이너에 접속하는 대역(RFC 6598) — 운영 access log 피어 전부가 이 안이었다.
# 이 피어가 준 X-Real-IP 만 믿는다.
# Railway's edge connects from this range (every measured prod peer); only its X-Real-IP is trusted.
_TRUSTED_PROXY_NETWORKS = (ipaddress.ip_network("100.64.0.0/10"),)  # NOSONAR python:S1313
# Railway 문서가 클라이언트 IP 로 명시한 헤더 — X-Forwarded-For 는 읽지 않는다(맨 왼쪽 값 스푸핑).
# The client-IP header Railway documents; X-Forwarded-For is deliberately not read.
_REAL_IP_HEADER = "x-real-ip"
# IPv6 가입자는 /64 를 통째로 받는다 — 주소 단위로 세면 한 사람이 버킷을 끝없이 만든다.
# An IPv6 subscriber owns a /64; per-address keys would let one client mint endless buckets.
_IPV6_BUCKET_PREFIX = 64

# 판정 결과별 프로세스당 1회만 로그 — 헤더 값(공격자 입력·PII)은 싣지 않고 고정 ASCII 만 쓴다.
# Log each outcome once per process with a fixed ASCII reason; never the header value.
_announced: set[str] = set()
_FALLBACK_NOTES = {
    "missing": "no X-Real-IP from trusted proxy; keying by uvicorn client address",
    "multiple": "several X-Real-IP lines; keying by uvicorn client address",
    "malformed": "unusable X-Real-IP; keying by uvicorn client address",
    "untrusted-peer": "X-Real-IP from a peer outside the trusted proxy range; keys may be client-derived",
}


def _announce(outcome: str) -> None:
    if outcome in _announced:
        return
    _announced.add(outcome)
    if outcome == "x-real-ip":
        logger.info("rate-limit key: X-Real-IP from trusted proxy peer")
    else:
        logger.warning("rate-limit key fallback (%s): %s", outcome, _FALLBACK_NOTES[outcome])


def _parse_ip(value: str):
    """IP 로 못 읽거나 zone id 가 붙으면 None. IPv4-mapped 는 IPv4 로 접는다.
    None when unparseable or scoped; an IPv4-mapped address folds to IPv4."""
    try:
        ip = ipaddress.ip_address(value.strip())
    except ValueError:
        return None
    if ip.version == 6:
        if ip.scope_id is not None:
            return None
        if ip.ipv4_mapped is not None:
            return ip.ipv4_mapped
    return ip


def _is_trusted_proxy(ip) -> bool:
    return any(ip in net for net in _TRUSTED_PROXY_NETWORKS)


def rate_limit_key(request: Request) -> str:
    """Railway 프록시 뒤 실제 클라이언트 기준 키. 애매하면 uvicorn 이 본 클라이언트 주소로 폴백한다.
    Key by the real client behind Railway's proxy; anything ambiguous falls back to uvicorn's client.

    폴백 값은 TCP 피어와 같다 — FORWARDED_ALLOW_IPS·--forwarded-allow-ips 가 미설정인 동안만.
    The fallback equals the TCP peer only while FORWARDED_ALLOW_IPS / --forwarded-allow-ips are unset.
    🔴 매개변수 이름은 `request` 여야 한다 — slowapi 가 이름으로 인자를 넘긴다.
    The parameter must be named `request`; slowapi dispatches on the name.
    🔴 빈 키면 slowapi 가 한도를 건너뛰고, 예외면 전 라우트 500 — 폴백은 늘 비어 있지 않은 주소다.
    slowapi skips the limit on an empty key and re-raises errors; every fallback is a non-empty address.
    """
    peer = get_remote_address(request)
    peer_ip = _parse_ip(peer)
    if peer_ip is None:
        return peer
    values = request.headers.getlist(_REAL_IP_HEADER)
    if not _is_trusted_proxy(peer_ip):
        # 엣지 대역 이동, 또는 uvicorn 이 client 를 XFF 로 바꿨다는 드리프트 신호
        # Drift tripwire: the edge left the range, or uvicorn rewrote the client from XFF.
        if values:
            _announce("untrusted-peer")
        return peer
    if len(values) != 1:
        _announce("missing" if not values else "multiple")
        return peer
    client_ip = _parse_ip(values[0])
    # 프록시 대역 값은 거절 — 헤더 키와 폴백 키를 서로소로 둔다(100.64.x 키 = 폴백)
    # Reject proxy-range values so header-derived keys never collide with fallback keys.
    if client_ip is None or _is_trusted_proxy(client_ip):
        _announce("malformed")
        return peer
    _announce("x-real-ip")
    if client_ip.version == 6:
        return str(ipaddress.IPv6Network((client_ip.packed, _IPV6_BUCKET_PREFIX), strict=False))
    return str(client_ip)


# 메모리 스토리지, .env 파일 읽기 비활성화 (Windows cp949 인코딩 충돌 방지)
# 🔴 key_func 는 데코레이션 시점에 각 라우트 Limit 에 복사된다 — 나중에 바꾸면 무효, 생성자에 넣는다.
# In-memory storage, no .env reading (cp949). slowapi copies key_func into each route at decoration.
limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri="memory://",
    config_filename="",  # .env 파일 자동 탐색 비활성화 / Disable automatic .env file lookup
)

# 엔드포인트 카테고리별 기본 제한 상수
# Default rate limit constants per endpoint category
RATE_LIMIT_API = "60/minute"    # 일반 API (repos 목록, stats 조회)
RATE_LIMIT_HEAVY = "10/minute"  # 무거운 API (분석 트리거, 대용량 연산)
