"""API Rate Limiting 테스트.
API rate limiting tests.
"""
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request as StarletteRequest
from uvicorn.config import Config
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.middleware import rate_limiter as rl
from tests.unit.scripts._dockerfile import DOCKERFILE, instructions, start_argv

# Railway 엣지 피어 대역(100.64.0.0/10) 안의 테스트 주소
# A test peer inside Railway's edge range (100.64.0.0/10)
_EDGE = "100.64.0.7"  # NOSONAR python:S1313


@pytest.fixture(autouse=True)
def _reset_key_announcements(monkeypatch):
    """판정 로그는 프로세스당 1회라 전역 상태다 — 테스트 순서가 로그 단언을 바꾸지 않게 매번 비운다.
    The once-per-process log state is module-global; reset it so test order cannot matter."""
    monkeypatch.setattr(rl, "_announced", set(), raising=False)


def test_rate_limiter_constants():
    """rate_limiter 모듈이 예상 상수를 export해야 한다.
    rate_limiter module must export expected constants.
    """
    from src.middleware.rate_limiter import limiter, RATE_LIMIT_API, RATE_LIMIT_HEAVY
    assert RATE_LIMIT_API == "60/minute"
    assert RATE_LIMIT_HEAVY == "10/minute"
    assert limiter is not None


def test_rate_limit_exceeded_returns_429():
    """제한 초과 시 429 Too Many Requests를 반환해야 한다.
    Must return 429 Too Many Requests when limit is exceeded.
    """
    test_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", config_filename="")
    app = FastAPI()
    app.state.limiter = test_limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/limited")
    @test_limiter.limit("2/minute")
    async def _limited(request: Request):  # pylint: disable=unused-argument
        return {"ok": True}

    client = TestClient(app, raise_server_exceptions=False)
    headers = {"X-Forwarded-For": "10.10.10.1"}  # NOSONAR python:S1313 — test-only private RFC-1918 address

    # 첫 두 번은 성공해야 함
    # First two calls must succeed
    assert client.get("/limited", headers=headers).status_code == 200
    assert client.get("/limited", headers=headers).status_code == 200
    # 세 번째는 429여야 함
    # Third call must return 429
    resp = client.get("/limited", headers=headers)
    assert resp.status_code == 429


def test_every_route_limit_uses_rate_limit_key():
    """🔴 slowapi 는 key_func 를 데코레이션 시점에 각 라우트 Limit 에 복사한다.

    그래서 `limiter._key_func` 만 보면 거짓 초록이다 — 살아 있는 라우트 레지스트리를 전수한다.
    slowapi binds key_func per route at decoration; walk the live registry, not just _key_func.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel

    assert app.routes, "라우트가 0개 — 앱이 조립되지 않았다"
    key = getattr(rl, "rate_limit_key", None)
    limits = [lim for lims in rl.limiter._route_limits.values() for lim in lims]  # pylint: disable=protected-access
    assert limits, "제한 등록 0개 — 이 검사가 공허하다"
    wrong = sorted({lim.key_func.__name__ for lim in limits if key is None or lim.key_func is not key})
    assert not wrong, f"rate_limit_key 가 아닌 key_func: {wrong} (#1691 — 프록시 주소 버킷)"
    assert rl.limiter._key_func is key  # pylint: disable=protected-access
    # 호출형 한도는 이 전수에서 빠진다 — 생기면 위 검사를 넓혀야 한다.
    # Callable (dynamic) limits escape the walk above; widen it before adding one.
    assert not rl.limiter._dynamic_route_limits  # pylint: disable=protected-access


def test_health_endpoint_no_rate_limit():
    """/health 엔드포인트는 rate limit 없이 반복 호출에도 200을 반환해야 한다.
    /health must always return 200 regardless of call frequency.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel

    client = TestClient(app, raise_server_exceptions=False)
    for _ in range(15):
        r = client.get("/health")
    assert r.status_code == 200


def test_app_state_has_limiter():
    """app.state.limiter가 설정되어 있어야 한다.
    app.state.limiter must be configured.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel

    assert hasattr(app.state, "limiter")
    assert app.state.limiter is limiter


# ─── 실제 엔드포인트 rate limit 적용 검증 ────────────────────────────────────
# Verifying rate limit decoration on real API endpoints

def test_rate_limited_endpoints_have_request_parameter():
    """rate limit 적용 엔드포인트의 서명에 request: Request가 있어야 한다.
    Rate-limited endpoint signatures must include request: Request (required by slowapi).

    slowapi는 첫 번째 파라미터 중 Request 타입을 찾아 IP를 추출한다.
    slowapi finds the Request-typed parameter to extract the client IP.
    """
    import inspect  # pylint: disable=import-outside-toplevel
    from src.api.repos import list_repos, list_repo_analyses  # pylint: disable=import-outside-toplevel
    from src.api.stats import get_analysis, get_repo_stats  # pylint: disable=import-outside-toplevel
    from fastapi import Request  # pylint: disable=import-outside-toplevel

    for fn in (list_repos, list_repo_analyses, get_analysis, get_repo_stats):
        sig = inspect.signature(fn)
        request_params = [
            p for p in sig.parameters.values()
            if p.annotation is Request or p.annotation == "Request"
        ]
        assert len(request_params) >= 1, (
            f"{fn.__name__}()에 request: Request 파라미터 없음 — slowapi 동작 불가"
        )


def test_429_response_has_json_body():
    """429 응답은 JSON body를 가져야 한다.
    429 response must have a JSON body.
    """
    test_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", config_filename="")
    test_app = FastAPI()
    test_app.state.limiter = test_limiter
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @test_app.get("/strict")
    @test_limiter.limit("1/minute")
    async def _strict(request: Request):  # pylint: disable=unused-argument
        return {"ok": True}

    client = TestClient(test_app, raise_server_exceptions=False)
    client.get("/strict")       # 성공 (1/minute 할당 소진) / first call uses the 1/minute quota
    resp = client.get("/strict")  # 429

    assert resp.status_code == 429
    # slowapi는 기본 JSON 오류 응답을 반환 / slowapi returns a JSON error response
    data = resp.json()
    assert "error" in data or "detail" in data or "message" in data


def test_429_response_content_type_is_json():
    """429 응답의 Content-Type이 application/json이어야 한다.
    429 response Content-Type must be application/json.

    slowapi 기본 설정에서 Retry-After 헤더는 미포함 (headers_enabled=False).
    slowapi default config does not include Retry-After (headers_enabled=False).
    """
    test_limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", config_filename="")
    test_app = FastAPI()
    test_app.state.limiter = test_limiter
    test_app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @test_app.get("/retry-after-test")
    @test_limiter.limit("1/minute")
    async def _retry(request: Request):  # pylint: disable=unused-argument
        return {"ok": True}

    client = TestClient(test_app, raise_server_exceptions=False)
    client.get("/retry-after-test")
    resp = client.get("/retry-after-test")  # 429

    assert resp.status_code == 429
    # slowapi 기본 설정: Content-Type은 JSON, Retry-After는 미포함 (headers_enabled=False 기본값)
    # slowapi default: JSON content type; Retry-After omitted when headers_enabled=False (default)
    assert "application/json" in resp.headers.get("content-type", "")


def test_rate_limiter_storage_is_in_memory():
    """rate_limiter는 메모리 스토리지를 사용해야 한다 (Redis 등 외부 의존성 없음).
    Rate limiter must use in-memory storage (no external dependency like Redis).
    """
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel

    storage_uri = str(getattr(limiter, "_storage_uri", "") or "")
    assert "memory" in storage_uri.lower() or storage_uri == "", (
        f"Rate limiter should use memory storage, got: {storage_uri}"
    )


# ─── 🔴 실제 라우트에서 정말 429 가 나는가 ──────────────────────────────────
#
# 위 검사들은 상수·장난감 `FastAPI()`·`app.state.limiter` 존재·서명 형태를 본다.
# 그중 어느 것도 **실제 API 라우트가 한도를 넘었을 때 429 를 돌려주는지** 확인하지 않는다.
# 데코레이터 한 줄이 사라져도 위 축은 전부 초록이다 — 그러면 무제한 호출이 열린다.
#
# None of the checks above prove a real route actually returns 429; losing one decorator
# leaves them all green while the endpoint becomes unbounded.

def test_real_route_returns_429_when_limit_exceeded():
    """실제 app 의 제한 라우트를 한도 초과로 두드리면 429 가 나온다.

    `/api/hook/verify` 를 쓰는 이유 — 인증 의존성이 없어 429 가 401 에 가려지지 않는다
    (limiter 는 미들웨어가 아니라 엔드포인트 데코레이터라 의존성 해결 뒤에 동작한다).
    Uses /api/hook/verify because it has no auth dependency, so the 429 is not masked by a 401.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel
    from src.middleware.rate_limiter import (  # pylint: disable=import-outside-toplevel
        RATE_LIMIT_API, limiter,
    )

    budget = int(RATE_LIMIT_API.split("/")[0])
    client = TestClient(app, raise_server_exceptions=False)

    # 🔴 memory:// 스토리지는 프로세스 전역 — 앞선 테스트의 잔여 카운트를 지우고 시작하고,
    #    끝나고도 지운다. 안 그러면 이 테스트가 남의 테스트를 429 로 떨어뜨린다.
    # The memory:// store is process-global; reset before and after so this test neither
    # inherits nor leaks counter state.
    limiter.reset()
    try:
        statuses = [
            client.get("/api/hook/verify", params={"repo": "o/r", "token": "t"}).status_code
            for _ in range(budget + 1)
        ]
    finally:
        limiter.reset()

    assert statuses[-1] == 429, (
        f"한도({RATE_LIMIT_API})를 {budget + 1}회로 넘겼는데 마지막 응답이 {statuses[-1]} — "
        "429 가 아니다. 이 라우트는 사실상 무제한이다."
    )
    assert 429 not in statuses[:budget], (
        f"한도 안({budget}회)에서 이미 429 — 제한이 과도하게 좁다: {statuses[:budget]}"
    )


def test_critical_mutating_routes_are_registered_with_the_limiter():
    """🔴 제한이 붙어야 하는 라우트가 레지스트리에 실재하는가.

    위 429 테스트는 라우트 **하나**를 증명한다. 나머지가 데코레이터를 잃어도 조용하다.
    slowapi 는 제한을 `limiter._route_limits` 에 `모듈.함수` 키로 기록하므로, 그 살아 있는
    레지스트리와 대조한다 — 소스 문자열(`"@limiter.limit" in src`) 검사가 아니다.

    Checks the live slowapi registry, not a source-string match.
    """
    from src.main import app  # pylint: disable=import-outside-toplevel
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel

    # app 을 실제로 참조한다 — 라우터 등록이 일어나야 레지스트리가 채워진다.
    # (side-effect import 를 noqa 로 숨기면 CodeQL py/unused-import 를 자초한다.)
    assert app.routes, "라우트가 0개 — 앱이 조립되지 않았다"

    registered = set(limiter._route_limits)  # pylint: disable=protected-access
    assert registered, "제한이 등록된 라우트가 0개 — 레지스트리가 비었다(이 검사가 공허하다)"

    # 돈·권한·외부 발신이 걸린 경로 — 무제한이 되면 비용/DoS 로 직결된다.
    # Routes tied to spend, permissions, or outbound calls.
    must_be_limited = {
        "src.api.repos.list_repos",
        "src.api.repos.update_repo_config",
        "src.api.repos.delete_repo_api",
        "src.api.hook.verify_hook",
        "src.api.stats.get_repo_stats",
        "src.api.issue_registration.register",
    }
    missing = sorted(must_be_limited - registered)
    assert not missing, (
        f"제한이 사라진 라우트: {missing}\n"
        f"→ 해당 엔드포인트에 @limiter.limit 를 되돌릴 것. 현재 등록됨={sorted(registered)}"
    )


# ─── 🔴 키는 Railway 프록시가 아니라 실제 클라이언트다 (#1691) ──────────────────
#
# 운영은 시작 명령의 `--proxy-headers` 로 uvicorn 의 실제 ProxyHeadersMiddleware 를 앞에 두고,
# FORWARDED_ALLOW_IPS 가 없어 엣지(100.64.0.0/10)의 X-Forwarded-For 를 믿지 않는다.
# 아래 하네스는 그 래핑을 그대로 재현하고, 실제 slowapi 데코레이터가 붙은 라우트를 두드린다.
# The harness reproduces production's wrapping (uvicorn's real ProxyHeadersMiddleware, no
# FORWARDED_ALLOW_IPS) and hits a route carrying the real slowapi decorator.

def _session_with_no_repo():
    # 미등록 리포 → verify_hook 는 결정적으로 404 (500 이 비-429 로 통과하지 못하게)
    # Unregistered repo -> a deterministic 404, so a 500 can never pass as "not 429".
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


@pytest.fixture
def deployed(monkeypatch):
    """운영 시작 명령(`--proxy-headers`)과 같은 래핑으로 앱을 띄운다. 인자 = TCP 피어 주소.
    Serve the app wrapped as in production; the argument is the TCP peer address."""
    from src.main import app  # pylint: disable=import-outside-toplevel

    monkeypatch.delenv("FORWARDED_ALLOW_IPS", raising=False)
    cfg = Config(app=app, proxy_headers=True, log_config=None)
    cfg.load()
    # uvicorn 이 래핑 방식을 바꾸면 조용히 우회하지 말고 여기서 깨진다
    # Break loudly if a future uvicorn stops wrapping this way.
    assert isinstance(cfg.loaded_app, ProxyHeadersMiddleware)
    rl.limiter.reset()
    with patch("src.api.hook.SessionLocal", return_value=_session_with_no_repo()):
        yield lambda peer=_EDGE: TestClient(cfg.loaded_app, raise_server_exceptions=False, client=(peer, 40000))
    rl.limiter.reset()


def _budget() -> int:
    return int(rl.RATE_LIMIT_API.split("/")[0])


def _hit(client, real_ip=None, **extra) -> int:
    headers = {"Authorization": "Bearer t", **extra}
    if real_ip is not None:
        headers["X-Real-IP"] = real_ip
    return client.get("/api/hook/verify", params={"repo": "o/r"}, headers=headers).status_code


def test_two_clients_behind_one_railway_proxy_do_not_share_a_bucket(deployed):
    """같은 엣지 피어 뒤의 두 클라이언트는 버킷을 나누지 않는다.
    Two clients behind the same edge peer get separate buckets."""
    c = deployed()
    spent = [_hit(c, "203.0.113.10") for _ in range(_budget() + 1)]
    # 양성 대조 — 한도가 실제로 걸린다
    # Positive control: the limit really applies.
    assert spent[:-1] == [404] * _budget() and spent[-1] == 429
    assert _hit(c, "198.51.100.20") == 404, "다른 사용자가 429 — 키가 엣지 프록시 주소다 (#1691)"


def test_rotating_x_forwarded_for_from_edge_cannot_mint_buckets(deployed):
    """엣지 피어가 매번 다른 X-Forwarded-For 를 실어도 uvicorn 은 그것을 client 로 쓰지 않는다.
    uvicorn must not adopt X-Forwarded-For from the edge; rotating it cannot escape the limit.

    forwarded-allow-ips 가 엣지를 믿게 되면 client 가 XFF 맨 왼쪽 값이 되어 매 요청 새 키다.
    If forwarded-allow-ips trusted the edge, each rotated XFF would become a fresh key."""
    c = deployed()
    statuses = [_hit(c, "203.0.113.10", **{"X-Forwarded-For": f"198.51.100.{i % 250 + 1}"})
                for i in range(_budget() + 1)]
    assert statuses[:-1] == [404] * _budget() and statuses[-1] == 429, (
        "XFF 를 바꿔 한도를 피했다 — uvicorn 이 엣지의 forwarded 헤더를 믿는다 (#1691)"
    )


def test_one_client_through_two_railway_proxies_shares_one_bucket(deployed):
    """한 클라이언트가 엣지 피어를 바꿔 들어와도 같은 버킷이다.
    One client arriving through two edge peers shares one bucket."""
    first, second = deployed("100.64.0.7"), deployed("100.64.0.8")  # NOSONAR python:S1313
    assert [_hit(first, "203.0.113.10") for _ in range(_budget())] == [404] * _budget()
    assert _hit(second, "203.0.113.10") == 429, "프록시를 바꾸면 한도가 초기화된다 — 피어당 버킷"


def test_ipv6_clients_bucket_per_64(deployed):
    """IPv6 는 /64 단위 버킷이다 — 위로도(/65·/96) 아래로도(/63) 넓이가 고정된다.
    IPv6 buckets are exactly /64: the second address differs at bit 65, the other /64 at bit 64."""
    c = deployed()
    assert [_hit(c, "2001:db8:1:2::1") for _ in range(_budget())] == [404] * _budget()
    # 65번째 비트가 다른 같은 /64 주소 — /65 이상으로 좁히면 새 버킷이 되어 red
    # Same /64, differs at bit 65: any prefix longer than /64 splits it and goes red.
    assert _hit(c, "2001:db8:1:2:8000::1") == 429, "같은 /64 안에서 주소를 바꿔 한도를 피했다"
    assert _hit(c, "2001:db8:1:3::1") == 404, "다른 /64 가 429 — 버킷이 공유된다"


# 루프백 · /10 바로 밖("100." 접두 판정 변이를 잡는다)
# Loopback, and the address just outside the /10 (catches a "100." prefix mutation).
@pytest.mark.parametrize("peer", ["127.0.0.1", "100.128.0.0"])  # NOSONAR python:S1313
def test_x_real_ip_from_untrusted_peer_cannot_mint_buckets(deployed, peer):
    """신뢰 대역 밖 피어의 X-Real-IP 로는 버킷을 만들 수 없다.
    An untrusted peer cannot mint buckets through X-Real-IP."""
    c = deployed(peer)
    statuses = [_hit(c, f"203.0.113.{i % 250 + 1}") for i in range(_budget() + 1)]
    assert statuses[-1] == 429, "신뢰 대역 밖 피어가 X-Real-IP 로 버킷을 무한 생성한다"


# 🔴 slowapi 는 빈 키면 `if all(args)` 에서 한도를 건너뛴다 — 폴백은 늘 비어 있지 않아야 한다.
# slowapi skips the limit on an empty key; every fallback must be non-empty.
@pytest.mark.parametrize("value", ["", "   ", None], ids=["empty", "blank", "missing"])
def test_empty_x_real_ip_from_edge_still_limited(deployed, value):
    """빈·공백·없는 X-Real-IP 는 피어 키로 폴백해 여전히 429 에 닿는다.
    Empty, blank or absent X-Real-IP falls back to the peer key and still reaches 429."""
    c = deployed()
    statuses = [_hit(c, value) for _ in range(_budget() + 1)]
    assert statuses[:-1] == [404] * _budget() and statuses[-1] == 429


def _req(peer, *values):
    scope = {"type": "http", "headers": [(b"x-real-ip", v.encode("latin-1")) for v in values]}
    if peer is not None:
        scope["client"] = (peer, 1)
    return StarletteRequest(scope)


def _key(request) -> str:
    # 라우트에 실제로 배선된 키 함수를 호출한다
    # Call the key function actually wired into the limiter.
    return rl.limiter._key_func(request)  # pylint: disable=protected-access


@pytest.mark.parametrize("values", [
    (), ("",), ("not-an-ip",), ("203.0.113.1, 198.51.100.2",), ("203.0.113.1:443",),
    ("203.0.113.1", "198.51.100.2"), ("fe80::1%eth0",),
    ("100.64.3.3",),  # NOSONAR python:S1313
    ("x" * 5000,),
], ids=["missing", "empty", "garbage", "comma", "port", "two-lines", "scoped", "proxy-range", "huge"])
def test_unusable_x_real_ip_falls_back_to_peer(values):
    """쓸 수 없는 X-Real-IP 는 전부 피어 주소로 폴백한다.
    Every unusable X-Real-IP falls back to the peer address."""
    assert _key(_req(_EDGE, *values)) == _EDGE


def test_padded_x_real_ip_is_trimmed_not_rejected():
    """앞뒤 공백만 붙은 유효 주소는 폴백이 아니라 그 주소로 키가 된다.
    A valid address with surrounding whitespace keys by that address, not the fallback."""
    assert _key(_req(_EDGE, " \t203.0.113.1 ")) == "203.0.113.1"


@pytest.mark.parametrize("peer,trusted", [
    ("100.64.0.0", True), ("100.127.255.255", True),  # NOSONAR python:S1313
    ("::ffff:100.64.0.9", True),  # NOSONAR python:S1313
    ("100.63.255.255", False), ("100.128.0.0", False),  # NOSONAR python:S1313
    ("testclient", False), (None, False),
])
def test_edge_cidr_boundaries(peer, trusted):
    """/10 경계 안쪽 피어만 X-Real-IP 를 쓴다 — 비 IP·없는 피어도 비어 있지 않은 키다.
    Only peers inside the /10 are trusted; non-IP or missing peers still yield a non-empty key."""
    key = _key(_req(peer, "203.0.113.1"))
    assert key and (key == "203.0.113.1") is trusted


def test_mapped_v4_client_folds_to_ipv4():
    """IPv4-mapped IPv6 클라이언트는 IPv4 키로 접힌다.
    An IPv4-mapped client folds to its IPv4 key."""
    assert _key(_req(_EDGE, "::ffff:203.0.113.1")) == "203.0.113.1"


def test_every_fallback_outcome_warns_even_when_first(caplog):
    """폴백 4종은 프로세스 첫 로그여도 전부 WARNING 이고, 헤더 채택 INFO 는 없다.
    All four fallback outcomes warn, even as the first record; no INFO without a used header."""
    with caplog.at_level(logging.INFO, logger=rl.__name__):
        _key(_req(_EDGE, "203.0.113.1", "198.51.100.2"))
        _key(_req(_EDGE))
        _key(_req(_EDGE, "not-an-ip"))
        _key(_req("198.51.100.9", "203.0.113.10"))
    mine = [r for r in caplog.records if r.name == rl.__name__]
    assert [(r.levelname, r.args[0]) for r in mine] == [
        ("WARNING", "multiple"), ("WARNING", "missing"),
        ("WARNING", "malformed"), ("WARNING", "untrusted-peer"),
    ]
    assert all(r.args[1] for r in mine), "폴백 WARNING 에 사유가 비었다"


def test_key_outcome_logged_once_without_header_values(caplog):
    """판정 결과별 로그는 1회이고 헤더 값은 싣지 않는다.
    Each outcome logs once and never carries the header value."""
    with caplog.at_level(logging.INFO, logger=rl.__name__):
        for _ in range(3):
            _key(_req(_EDGE, "203.0.113.10"))
        for _ in range(2):
            _key(_req(_EDGE, "not-an-ip"))
        _key(_req("198.51.100.9", "203.0.113.10"))
    mine = [r for r in caplog.records if r.name == rl.__name__]
    assert [r.levelname for r in mine] == ["INFO", "WARNING", "WARNING"]
    assert [r.args[0] for r in mine[1:]] == ["malformed", "untrusted-peer"]
    # 신뢰 대역 밖 피어 = uvicorn 이 클라이언트를 XFF 로 바꿨을 수 있다 → 키가 클라이언트 입력일 수 있다
    # An untrusted peer may mean uvicorn rewrote the client from XFF: keys may be client-derived.
    assert "client-derived" in mine[2].getMessage()
    leaked = [r.getMessage() for r in mine if "203.0.113" in r.getMessage() or "not-an-ip" in r.getMessage()]
    assert not leaked, f"헤더 값이 로그에 실렸다: {leaked}"


# 🔴 폴백 키는 «uvicorn 이 본 클라이언트» 다. forwarded-allow-ips 로 엣지를 믿으면 uvicorn 이
# 클라이언트가 쓴 X-Forwarded-For 맨 왼쪽 값으로 client 를 바꾸고, 그 값이 곧 키가 된다(한도 우회).
# The fallback key is uvicorn's view of the client; trusting the edge makes it client-controlled XFF.
def _widens_forwarded_trust(start_command: str) -> bool:
    return "forwarded-allow-ips" in start_command.lower() or "forwarded_allow_ips" in start_command.lower()


@pytest.mark.parametrize("command", [
    "uvicorn src.main:app --proxy-headers --forwarded-allow-ips='*'",
    "FORWARDED_ALLOW_IPS=* uvicorn src.main:app --proxy-headers",
    "UVICORN_FORWARDED_ALLOW_IPS=* uvicorn src.main:app --proxy-headers",
])
def test_forwarded_trust_detector_catches_synthetic_violation(command):
    """탐지기가 합성 위반 3형태를 잡는다 — 아래 가드가 공허하지 않다는 근거.
    The detector catches three synthetic violations, so the guard below is not vacuous."""
    assert _widens_forwarded_trust(command)


def test_image_does_not_trust_forwarded_headers():
    """이미지 CMD·ENV 는 forwarded-allow-ips 를 넓히지 않는다 — 대시보드 Start Command 는 저장소 밖이다.
    The image CMD and ENV never widen forwarded-allow-ips; the dashboard start command lives outside the repo."""
    text = DOCKERFILE.read_text(encoding="utf-8")
    cmd = " ".join(start_argv(text) or [])
    assert "--proxy-headers" in cmd, "이미지 CMD 형태가 바뀌었다 — 이 가드의 전제를 다시 볼 것"
    # ENV·ARG·CMD 어디에 넣어도 uvicorn 이 읽는다 — 주석을 뺀 지시어 전부를 본다.
    # uvicorn reads it from ENV, ARG or CMD alike, so every non-comment instruction is checked.
    live = " ".join(f"{keyword} {args}" for keyword, args in instructions(text))
    assert not _widens_forwarded_trust(live), (
        "Dockerfile 이 forwarded-allow-ips 를 넓혔다 — 레이트리밋 키가 스푸핑 가능해진다 (#1691)"
    )
