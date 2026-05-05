"""alembic dialect helper 회귀 가드 (Cycle 82 PR 1 — Tier B 정정).

5+1 cross-verify (사이클 78~81 회고) Tier B = `dialect.name == "postgresql"` 사용처 12건
helper 추출 (정책 16 4번 원칙 정합).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.shared.alembic_dialect import is_postgresql


class TestIsPostgresql:
    """is_postgresql — bind/connection 객체 duck typing PG 검사."""

    def test_pg_bind_returns_true(self):
        """op.get_bind() 패턴 — bind.dialect.name == 'postgresql'."""
        bind = MagicMock()
        bind.dialect.name = "postgresql"
        assert is_postgresql(bind) is True

    def test_sqlite_bind_returns_false(self):
        """SQLite 단위 테스트 환경 — 자동 skip."""
        bind = MagicMock()
        bind.dialect.name = "sqlite"
        assert is_postgresql(bind) is False

    def test_mysql_bind_returns_false(self):
        """MySQL 환경 — PG 전용 DDL skip."""
        bind = MagicMock()
        bind.dialect.name = "mysql"
        assert is_postgresql(bind) is False

    def test_pg_connection_returns_true(self):
        """SQLAlchemy Connection (database.py event listener / env.py) 패턴."""
        conn = MagicMock()
        conn.dialect.name = "postgresql"
        assert is_postgresql(conn) is True

    def test_op_get_context_returns_true_when_dialect_pg(self):
        """op.get_context() 패턴 — context.dialect.name == 'postgresql' 호환."""
        context = MagicMock()
        context.dialect.name = "postgresql"
        assert is_postgresql(context) is True

    def test_no_dialect_attribute_returns_false(self):
        """dialect 속성 부재 객체 = False (defensive — 정책 16 정확성 default)."""
        obj = object()  # dialect 속성 없음
        assert is_postgresql(obj) is False

    def test_dialect_no_name_returns_false(self):
        """dialect 속성 있으나 name 부재 = False (defensive)."""
        obj = MagicMock()
        del obj.dialect.name
        # MagicMock 의 attribute access 는 자동 MagicMock 반환 — 명시 set 의무
        obj.dialect = MagicMock(spec=[])
        assert is_postgresql(obj) is False

    def test_none_returns_false(self):
        """None 입력 = False (defensive)."""
        assert is_postgresql(None) is False

    @pytest.mark.parametrize("dialect_name", [
        "sqlite", "mysql", "mariadb", "oracle", "mssql", "", "POSTGRESQL",  # 대문자 = case-sensitive
    ])
    def test_non_pg_dialects_return_false(self, dialect_name):
        """PostgreSQL 외 dialect = False (case-sensitive — 'postgresql' 정확 매칭만)."""
        bind = MagicMock()
        bind.dialect.name = dialect_name
        assert is_postgresql(bind) is False
