"""alembic dialect 분기 helper — PG 전용 DDL skip 가드.

Cycle 82 PR 1 — 사이클 78~81 회고 cross-verify Tier B 정정 (정책 16 4번 원칙 정합).
Cycle 78~81 회고 cross-verify Tier B fix (Policy 16 principle #4 compliance).

5+1 cross-verify 결과 = `dialect.name == "postgresql"` 사용처 12건 (alembic 9 +
database.py 1 + env.py 2) — 정책 16 4번 원칙 (사용처 ≥ 3 도달 시 헬퍼 추출) 명백
도달. 사이클 64 회고 보류 결정 정정 시점 (사용처 2 → 12).

5+1 cross-verify finding = `dialect.name == "postgresql"` usage 12 sites (alembic 9
+ database.py 1 + env.py 2) — Policy 16 principle #4 (extract helper at usage ≥ 3)
threshold clearly reached. Cycle 64 retro deferred decision now overturned.

사용 패턴:
    # alembic 마이그레이션 (op.get_bind() 패턴)
    from src.shared.alembic_dialect import is_postgresql
    def upgrade():
        if not is_postgresql(op.get_bind()):
            return  # SQLite 단위 테스트 skip
        op.execute(_RLS_SQL)

    # alembic env.py (connection 직접)
    if is_postgresql(connection):
        # PG 전용 처리

    # src/database.py event listener (conn 직접)
    if not is_postgresql(conn):
        return
"""
from __future__ import annotations

from typing import Any


def is_postgresql(bind_or_conn: Any) -> bool:
    """alembic bind/connection 객체가 PostgreSQL dialect 인지 검사 (duck typing).

    Check whether alembic bind/connection object uses PostgreSQL dialect (duck typed).

    Args:
        bind_or_conn: 다음 객체 중 하나 — duck typing 으로 모두 호환:
            - `op.get_bind()` (alembic 마이그레이션 — 0024/0027/0028/0029 패턴)
            - `op.get_context()` (alembic 마이그레이션 — 0026 패턴)
            - SQLAlchemy `Connection` (src/database.py event listener / env.py)

    Returns:
        True if dialect.name == "postgresql", False otherwise (SQLite/MySQL/etc).

    Note:
        op.get_context() 패턴은 dialect 가 직접 노출 안 됨 — 별도 처리 의무.
        For op.get_context() the dialect is one level deeper (`.dialect.name`).
        본 helper 는 `.dialect.name` 직접 접근 — get_context 영역은 caller 가
        `is_postgresql(op.get_context())` 호출 시 동작 보장 (dialect 속성 통합).
    """
    dialect = getattr(bind_or_conn, "dialect", None)
    if dialect is None:
        return False
    return getattr(dialect, "name", "") == "postgresql"
