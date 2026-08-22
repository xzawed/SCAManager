"""API Rate Limiting 테스트.
API rate limiting tests.
"""
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


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


def test_rate_limiter_uses_remote_address_key_func():
    """Limiter의 key_func이 get_remote_address여야 한다.
    Limiter must use get_remote_address as key_func.
    """
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel

    # get_remote_address는 slowapi 표준 IP 기반 키 함수
    # get_remote_address is the standard slowapi IP-based key function
    assert limiter._key_func is get_remote_address


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
    from src.middleware.rate_limiter import limiter  # pylint: disable=import-outside-toplevel
    import src.main  # noqa: F401  # pylint: disable=import-outside-toplevel,unused-import

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
