"""RLS session middleware — request 시작 시 session.user_id 를 contextvars 로 전파.

request 시작 시 session.user_id (Starlette SessionMiddleware 가 scope["session"] 에 채움)
를 추출해 `src.shared.rls_context._RLS_USER_ID` 에 저장. request 종료 시 reset.

SQLAlchemy event listener (`src/database.py::_set_rls_user_id_per_query`) 가
매 query 직전에 본 contextvars 읽고 `SET LOCAL app.user_id = '<id>'` 발화 (PG only).

Phase 3 postlude — alembic 0026 RLS policy (메모리 `phase3-rls-runtime-activation-pending.md`)
운영 활성화. 본 미들웨어 부재 시 RLS = "deny-all + legacy admin only 모드" 동작 (운영 사고 위험).

🔴 ASGI middleware 패턴 의무 (BaseHTTPMiddleware 우회):
Starlette `BaseHTTPMiddleware.dispatch` 는 별도 anyio task 에서 `call_next` 호출 →
contextvars 가 하위 라우트 핸들러에 전파 X. 본 미들웨어는 동일 task ASGI 패턴 사용.

ASGI middleware (not BaseHTTPMiddleware) — same task ensures contextvars propagate to handlers.
"""
from src.shared.rls_context import reset_rls_user_id, set_rls_user_id


class RLSSessionMiddleware:  # pylint: disable=too-few-public-methods
    """ASGI middleware — request 시작 시 scope["session"]["user_id"] → contextvars.

    ASGI 표준 = `__call__` 단일 method (pylint R0903 inline disable — 의도된 표준 패턴).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # HTTP scope 만 처리 (websocket / lifespan 무관)
        # Only handle HTTP scope (websocket / lifespan are not affected)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # session 에서 user_id 추출 — Starlette SessionMiddleware 가 먼저 등록되어야 함
        # Extract user_id from session — Starlette SessionMiddleware must be registered first
        user_id: int | None = None
        try:
            session = scope.get("session", {})
            raw = session.get("user_id") if session else None
            if raw is not None:
                user_id = int(raw)
        except (KeyError, ValueError, TypeError, AttributeError):
            # session 부재 / 키 없음 / int 변환 실패 모두 graceful
            # session missing / key absent / int conversion failure all graceful
            user_id = None

        token = set_rls_user_id(user_id)
        try:
            await self.app(scope, receive, send)
        finally:
            # request 종료 시 cleanup — cross-request 격리 보장
            # Cleanup at request end — cross-request isolation guaranteed
            reset_rls_user_id(token)
