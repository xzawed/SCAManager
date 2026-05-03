"""RLS user_id context — request scope (Phase 3 postlude).

contextvars 기반 request scope user_id 컨텍스트.
SQLAlchemy event listener 가 매 query 직전에 본 컨텍스트 읽고 `SET LOCAL app.user_id` 발화.

Request-scoped user_id context for RLS. The SQLAlchemy event listener reads this
on every query and emits `SET LOCAL app.user_id`. None = anonymous/unauthenticated.

Phase 3 postlude — RLS 운영 활성화 미들웨어. alembic 0026 의 USING 절이
`current_setting('app.user_id', true)` 의존 — 본 컨텍스트 미설정 시 RLS = "deny-all + legacy admin only" 동작.
"""
import contextvars

# request scope user_id (None = 익명/미인증)
# Request-scoped user_id (None = anonymous/unauthenticated)
_RLS_USER_ID: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "rls_user_id", default=None
)


def set_rls_user_id(user_id: int | None) -> contextvars.Token:
    """user_id 를 contextvars 에 설정. 반환 token 은 reset 에 사용.

    Set user_id in contextvars. Returned token is used for reset.
    """
    return _RLS_USER_ID.set(user_id)


def get_rls_user_id() -> int | None:
    """현재 request 의 user_id 반환 (None = 익명).

    Return current request's user_id (None = anonymous).
    """
    return _RLS_USER_ID.get()


def reset_rls_user_id(token: contextvars.Token) -> None:
    """token 으로 contextvars reset (request scope cleanup).

    Reset contextvars using token (request scope cleanup).
    """
    _RLS_USER_ID.reset(token)
