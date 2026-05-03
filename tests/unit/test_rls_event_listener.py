"""RLS SQLAlchemy event listener 단위 테스트 — Phase 3 RLS 운영 활성화.

`SET LOCAL app.user_id` 발화 조건과 graceful 동작 검증.
SQLAlchemy event listener tests — verifies that `SET LOCAL app.user_id`
is emitted only on PostgreSQL, falls back to empty string for anonymous
requests, and never breaks query execution if contextvars introspection
raises.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Red 단계: src.database._set_rls_user_id_per_query 미존재 → ImportError
# Red phase: src.database._set_rls_user_id_per_query does not exist yet,
# so this import is the intended failure signal.
from src.database import _set_rls_user_id_per_query  # noqa: E402
from src.shared.rls_context import (  # noqa: E402
    reset_rls_user_id,
    set_rls_user_id,
)


@pytest.fixture
def mock_pg_conn():
    """PostgreSQL dialect 를 흉내내는 mock connection.
    Mock SQLAlchemy connection mimicking the PostgreSQL dialect.
    """
    conn = MagicMock()
    conn.dialect.name = "postgresql"
    return conn


@pytest.fixture
def mock_sqlite_conn():
    """SQLite dialect 를 흉내내는 mock connection.
    Mock SQLAlchemy connection mimicking the SQLite dialect.
    """
    conn = MagicMock()
    conn.dialect.name = "sqlite"
    return conn


@pytest.fixture
def mock_cursor():
    """SET LOCAL 호출 발화 여부 검증용 mock cursor.
    Mock cursor used to assert whether SET LOCAL was issued.
    """
    return MagicMock()


@pytest.fixture(autouse=True)
def _reset_rls_context():
    """각 테스트 직전/직후 contextvars 를 None 으로 초기화.
    Reset contextvars to None around every test to keep cases isolated.
    """
    token = set_rls_user_id(None)
    yield
    reset_rls_user_id(token)


# ---------------------------------------------------------------------------
# B.1 — SQLite dialect 에서는 SQL 발화 X (개발/테스트 환경 호환)
# B.1 — listener must skip SQL execution on SQLite to keep dev/test compatible
# ---------------------------------------------------------------------------
def test_listener_skips_on_sqlite_dialect(mock_sqlite_conn, mock_cursor):
    # SQLite 에는 SET LOCAL 문법이 없으므로 listener 는 즉시 return 해야 함
    # SQLite has no SET LOCAL syntax, so the listener must return immediately.
    _set_rls_user_id_per_query(
        mock_sqlite_conn, mock_cursor, "SELECT 1", {}, None, False
    )
    mock_cursor.execute.assert_not_called()


# ---------------------------------------------------------------------------
# B.2 — PostgreSQL + user_id 설정 시 정확한 SET LOCAL SQL 발화
# B.2 — emits the exact SET LOCAL statement on PostgreSQL with user_id
# ---------------------------------------------------------------------------
def test_listener_emits_set_local_on_postgresql_with_user_id(
    mock_pg_conn, mock_cursor
):
    # contextvars 에 42 설정 후 listener 호출 → cursor.execute 인자 검증
    # Set contextvars to 42, invoke listener, then assert the exact SQL emitted.
    set_rls_user_id(42)
    _set_rls_user_id_per_query(
        mock_pg_conn, mock_cursor, "SELECT 1", {}, None, False
    )
    mock_cursor.execute.assert_called_once_with("SET LOCAL app.user_id = '42'")


# ---------------------------------------------------------------------------
# B.3 — PostgreSQL + user_id 미설정 시 빈 문자열로 발화 (RLS deny-all)
# B.3 — anonymous PostgreSQL request emits empty string (RLS deny-all default)
# ---------------------------------------------------------------------------
def test_listener_emits_empty_on_postgresql_no_user(mock_pg_conn, mock_cursor):
    # contextvars 가 None (anonymous) 일 때 SET LOCAL 의 값은 빈 문자열이어야 함
    # When contextvars is None (anonymous), SET LOCAL must use an empty string.
    # 기본값이 None — autouse fixture 가 보장하므로 별도 set 불필요
    # Default is None — already enforced by the autouse fixture.
    _set_rls_user_id_per_query(
        mock_pg_conn, mock_cursor, "SELECT 1", {}, None, False
    )
    mock_cursor.execute.assert_called_once_with("SET LOCAL app.user_id = ''")


# ---------------------------------------------------------------------------
# B.4 — get_rls_user_id() 가 예외 raise 해도 listener 는 graceful (query 차단 X)
# B.4 — listener stays graceful when get_rls_user_id() raises (no query break)
# ---------------------------------------------------------------------------
def test_listener_does_not_break_on_get_context_failure(mock_pg_conn, mock_cursor):
    # contextvars 조회 자체가 실패해도 listener 는 예외를 propagate 하면 안 됨
    # Even if contextvars introspection itself fails, the listener must not
    # propagate the exception — query path stays intact.
    with patch(
        "src.database.get_rls_user_id",
        side_effect=RuntimeError("contextvars broken"),
    ):
        # 예외가 propagate 되면 본 테스트는 fail (pytest.raises 미사용 = no-raise 검증)
        # If the exception propagated, this test would fail — the absence of
        # pytest.raises is the no-raise assertion.
        _set_rls_user_id_per_query(
            mock_pg_conn, mock_cursor, "SELECT 1", {}, None, False
        )
