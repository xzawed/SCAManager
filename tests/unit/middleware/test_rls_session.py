"""RLSSessionMiddleware 단위 테스트 — Phase 3 RLS 운영 활성화.

세션 user_id → contextvars 전파 + request 종료 시 cleanup 검증.
RLSSessionMiddleware unit tests for Phase 3 RLS production enablement —
verifies session.user_id propagation into contextvars and cleanup on
request completion.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

# Red 단계: 신규 모듈 미존재 → ImportError 발생 (의도된 fail).
# Red phase: new modules do not exist yet, so these imports trigger
# ImportError as the intended failure signal.
from src.shared.rls_context import (  # noqa: E402
    get_rls_user_id,
    reset_rls_user_id,
    set_rls_user_id,
)
from src.middleware.rls_session import RLSSessionMiddleware  # noqa: E402


# ---------------------------------------------------------------------------
# A.1 — contextvars 초기값 검증
# A.1 — verifies the initial contextvars value is None
# ---------------------------------------------------------------------------
def test_rls_context_initial_value_is_none():
    # 어떤 set 호출도 없는 상태에서 default 가 None 이어야 함
    # The default value must be None when no set has been performed yet.
    # 격리: 다른 테스트가 set 한 뒤 reset 안 했을 가능성에 대비해 강제 None 으로 설정 후 측정
    # Isolation guard: defensively force None in case a previous test left a stale value.
    token = set_rls_user_id(None)
    try:
        assert get_rls_user_id() is None
    finally:
        reset_rls_user_id(token)


# ---------------------------------------------------------------------------
# A.2 — set/get/reset 사이클 검증
# A.2 — verifies the full set/get/reset lifecycle
# ---------------------------------------------------------------------------
def test_rls_context_set_and_get():
    # set 직후 동일 값을 get 해야 함 + reset 후 다시 None 으로 복귀해야 함
    # After set, get must return the same value; after reset, it must revert to None.
    token = set_rls_user_id(42)
    assert get_rls_user_id() == 42
    reset_rls_user_id(token)
    assert get_rls_user_id() is None


# ---------------------------------------------------------------------------
# 공용 헬퍼 — RLSSessionMiddleware 단독 테스트 앱 (main.py 의존 회피)
# Helper — standalone TestClient app for middleware-only assertions
# (avoids depending on src.main wiring during the Red phase).
# ---------------------------------------------------------------------------
def _build_test_app() -> FastAPI:
    """RLSSessionMiddleware 만 적용된 최소 FastAPI 앱.
    Minimal FastAPI app wired with only RLSSessionMiddleware + SessionMiddleware,
    exposing two endpoints used to introspect contextvars during a request.
    """
    test_app = FastAPI()
    # Starlette LIFO: 마지막 add 가 outer → SessionMiddleware 가 RLS 보다 outer 가 되어야 함.
    # Therefore RLS first (inner), SessionMiddleware last (outer) — request 흐름:
    # SessionMiddleware → RLSSessionMiddleware → route (RLS 가 채워진 session 읽음).
    test_app.add_middleware(RLSSessionMiddleware)
    test_app.add_middleware(SessionMiddleware, secret_key="test-rls-secret-32-chars-long!!")

    @test_app.get("/_set-session")
    async def _set_session(request: Request, user_id: int):  # type: ignore[no-untyped-def]
        # 세션에 user_id 주입 — 다음 요청에서 middleware 가 이를 contextvars 로 옮긴다
        # Inject user_id into the session so subsequent requests propagate it via contextvars.
        request.session["user_id"] = user_id
        return JSONResponse({"ok": True})

    @test_app.get("/_read-rls")
    async def _read_rls():
        # request 처리 중 contextvars 값을 그대로 응답
        # Echo the contextvars value observed during request handling.
        return JSONResponse({"user_id": get_rls_user_id()})

    return test_app


# ---------------------------------------------------------------------------
# A.3 — middleware 가 session.user_id 를 contextvars 로 전파
# A.3 — middleware copies session.user_id into contextvars during request handling
# ---------------------------------------------------------------------------
def test_rls_middleware_sets_contextvars_from_session():
    # 1) 첫 요청으로 세션 쿠키 발급 + user_id=42 주입
    # 1) First request issues a session cookie and stores user_id=42.
    # 2) 두 번째 요청에서 middleware 가 contextvars 에 42 를 올려야 함
    # 2) Second request should expose user_id=42 via contextvars.
    client = TestClient(_build_test_app())
    setup = client.get("/_set-session", params={"user_id": 42})
    assert setup.status_code == 200

    response = client.get("/_read-rls")
    assert response.status_code == 200
    assert response.json() == {"user_id": 42}


# ---------------------------------------------------------------------------
# A.4 — 세션 없는 요청은 contextvars 가 None 으로 유지
# A.4 — anonymous request keeps contextvars at None
# ---------------------------------------------------------------------------
def test_rls_middleware_no_session_returns_none_user():
    # 신규 client (쿠키 없음) → session.user_id 부재 → middleware 는 None 으로 처리
    # A fresh client has no session cookie, so middleware must yield None.
    client = TestClient(_build_test_app())
    response = client.get("/_read-rls")
    assert response.status_code == 200
    assert response.json() == {"user_id": None}


# ---------------------------------------------------------------------------
# A.5 — request 완료 시 contextvars 가 cleanup + 다음 요청 격리 보장
# A.5 — contextvars are cleaned up after each request, isolating later requests
# ---------------------------------------------------------------------------
def test_rls_middleware_cleans_up_after_request():
    # 1) client A 요청으로 user_id=10 설정 후 read 검증
    # 1) Client A sets user_id=10 and verifies the propagated value.
    # 2) 동일 프로세스에서 client B (다른 세션) 요청이 None 으로 격리되어야 함
    # 2) A separate Client B (different session) must observe None — no cross-talk.
    # 3) request 종료 후 contextvars 가 None 으로 reset 되었는지 직접 확인
    # 3) After requests complete, contextvars must reset to None at module scope.
    app_a = _build_test_app()
    client_a = TestClient(app_a)
    client_a.get("/_set-session", params={"user_id": 10})
    response_a = client_a.get("/_read-rls")
    assert response_a.json() == {"user_id": 10}

    # 새 client (별도 cookie jar) — session 없음 → contextvars cross-talk 가 있다면 10 이 새어 나옴
    # Fresh client (separate cookie jar) with no session — if contextvars leaked,
    # we would observe 10; the assertion guards against cross-request bleed.
    client_b = TestClient(app_a)
    response_b = client_b.get("/_read-rls")
    assert response_b.json() == {"user_id": None}

    # 모든 요청 종료 후 모듈 레벨에서 contextvars 는 None 이어야 함
    # After all requests finish, the module-level contextvars must be None.
    assert get_rls_user_id() is None
