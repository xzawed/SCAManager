"""saas_service — Cycle 79 PR 3a 회귀 가드.

tenant_inventory + rls_audit_matrix + rls_coverage_summary.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.services import saas_service
from src.services.saas_service import _RLS_MATRIX


@pytest.fixture
def db():
    """In-memory SQLite + 단위 격리."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


# ─── tenant_inventory ────────────────────────────────────────────────


class TestTenantInventory:
    def test_empty_db_returns_empty_list(self, db):
        assert saas_service.tenant_inventory(db) == []

    def test_user_with_no_repos(self, db):
        u = User(github_login="alice", github_id=1, email="alice@example.com", display_name="Alice")
        db.add(u)
        db.commit()
        result = saas_service.tenant_inventory(db)
        assert len(result) == 1
        assert result[0]["github_login"] == "alice"
        assert result[0]["repo_count"] == 0
        assert result[0]["analysis_count"] == 0
        assert result[0]["last_analysis_at"] is None

    def test_user_with_repos_and_analyses(self, db):
        u = User(github_login="alice", github_id=1, email="alice@example.com", display_name="Alice")
        db.add(u)
        db.commit()
        db.refresh(u)
        r = Repository(full_name="alice/repo1", user_id=u.id)
        db.add(r)
        db.commit()
        db.refresh(r)
        for i in range(3):
            db.add(Analysis(
                repo_id=r.id, commit_sha=("a" * 40 if i == 0 else "b" * 40 if i == 1 else "c" * 40),
                score=80 + i, grade="B",
            ))
        db.commit()
        result = saas_service.tenant_inventory(db)
        assert len(result) == 1
        assert result[0]["repo_count"] == 1
        assert result[0]["analysis_count"] == 3
        assert result[0]["last_analysis_at"] is not None

    def test_multiple_users_isolation(self, db):
        u1 = User(github_login="alice", github_id=1, email="alice@example.com", display_name="Alice")
        u2 = User(github_login="bob", github_id=2, email="bob@example.com", display_name="Bob")
        db.add_all([u1, u2])
        db.commit()
        db.refresh(u1)
        db.refresh(u2)
        # alice = 2 repos, bob = 1 repo
        for full_name in ("alice/r1", "alice/r2"):
            db.add(Repository(full_name=full_name, user_id=u1.id))
        db.add(Repository(full_name="bob/r1", user_id=u2.id))
        db.commit()
        result = saas_service.tenant_inventory(db)
        assert len(result) == 2
        # 정렬 = User.id 오름차순
        assert result[0]["github_login"] == "alice"
        assert result[0]["repo_count"] == 2
        assert result[1]["github_login"] == "bob"
        assert result[1]["repo_count"] == 1


# ─── rls_audit_matrix ────────────────────────────────────────────────


class TestRlsAuditMatrix:
    def test_returns_11_tables(self):
        matrix = saas_service.rls_audit_matrix()
        assert len(matrix) == 11  # 0026 (3) + 0027 (1) + 0028 (1) + 0029 (5) + 0037 (1)

    def test_all_tables_applied(self):
        matrix = saas_service.rls_audit_matrix()
        for entry in matrix:
            assert entry["status"] == "applied"

    def test_includes_5_alembic_0029_tables(self):
        matrix = saas_service.rls_audit_matrix()
        tables_in_0029 = [m["table"] for m in matrix if m["since"] == "0029"]
        assert set(tables_in_0029) == {
            "users", "repo_configs", "gate_decisions",
            "merge_retry_queue", "analysis_feedbacks",
        }

    def test_includes_issue_registrations_0037(self):
        """0037 issue_registrations RLS 항목이 매트릭스에 등재됐는지 확인."""
        matrix = saas_service.rls_audit_matrix()
        entry = next((m for m in matrix if m["table"] == "issue_registrations"), None)
        assert entry is not None, "issue_registrations 매트릭스 누락 (alembic 0037 적용됨)"
        assert entry["since"] == "0037"
        assert entry["status"] == "applied"


class TestRlsCoverageSummary:
    def test_summary_counts(self):
        summary = saas_service.rls_coverage_summary()
        assert summary["total"] == 11
        assert summary["applied"] == 11
        assert summary["missing"] == 0

    # ── RLS Phase 3 — force_applied 실측 (pg_class.relforcerowsecurity) ──
    # ── RLS Phase 3 — force_applied live-check (pg_class.relforcerowsecurity) ──

    def _pg_mock(self, forced_count: int, bypasses: bool = False) -> MagicMock:
        """postgresql dialect mock 세션 — 쿼리별 결과 주입 헬퍼.

        relforcerowsecurity 카운트(force 실측)와 rolbypassrls/rolsuper(우회 실측)를
        SQL 본문으로 분기해 각각 주입한다 — 두 쿼리가 한 summary 호출에서 공존하므로
        단일 return_value 로는 구분 불가.
        PostgreSQL-dialect mock session — injects per-query results. The force count
        (relforcerowsecurity) and the bypass flag (rolbypassrls/rolsuper) are routed
        by SQL text, since both queries run inside one summary call.
        """
        mock_db = MagicMock()
        mock_db.get_bind.return_value.dialect.name = "postgresql"

        def _route(statement, *_args, **_kwargs):
            result = MagicMock()
            if "relforcerowsecurity" in str(statement):
                result.scalar.return_value = forced_count
            else:
                result.scalar.return_value = bypasses
            return result

        mock_db.execute.side_effect = _route
        return mock_db

    def test_summary_force_false_without_db(self):
        """무인자 호출 시 force_applied=False — 하위 호환 가드 (db 미전달 호출처 보호).

        Calling without a db must keep force_applied=False — backward-compat guard
        protecting callers that pass no session.
        """
        summary = saas_service.rls_coverage_summary()
        assert summary["force_applied"] is False

    def test_summary_force_false_on_sqlite_session(self, db):
        """SQLite 실 세션 전달 시 비-PostgreSQL → force_applied=False (단위 테스트 호환).

        A real SQLite session (non-PostgreSQL) must yield force_applied=False
        (keeps unit tests dialect-safe).
        """
        summary = saas_service.rls_coverage_summary(db)
        assert summary["force_applied"] is False

    def test_summary_force_true_on_postgresql_all_forced(self):
        """PG + relforcerowsecurity=true 11/11 → force_applied=True (실측 양성 경로).

        PG with 11/11 relforcerowsecurity=true must report force_applied=True.
        total/applied/missing 기존 키 동작 불변도 함께 고정.
        Also pins that total/applied/missing keys stay unchanged.
        """
        summary = saas_service.rls_coverage_summary(self._pg_mock(11))
        assert summary["force_applied"] is True
        # 기존 키 불변 — force 실측 도입이 카운트 키를 깨지 않아야 한다
        # Existing keys unchanged — the live check must not break the count keys
        assert summary["total"] == 11
        assert summary["applied"] == 11
        assert summary["missing"] == 0

    def test_summary_force_false_on_postgresql_partial(self):
        """PG + relforcerowsecurity=true 10/11 (부분 적용) → force_applied=False.

        PG with only 10/11 forced tables (partial) must report force_applied=False.
        """
        summary = saas_service.rls_coverage_summary(self._pg_mock(10))
        assert summary["force_applied"] is False

    # ── connection_bypasses_rls 실측 — Phase 3~4 거짓 안심 창 가시화 ──
    # ── connection_bypasses_rls live-check — Phase 3~4 false-confidence window ──

    def test_summary_bypass_false_without_db(self):
        """무인자 호출 시 connection_bypasses_rls=False (하위 호환 가드).

        Calling without a db must keep connection_bypasses_rls=False (backward compat).
        """
        summary = saas_service.rls_coverage_summary()
        assert summary["connection_bypasses_rls"] is False

    def test_summary_bypass_false_on_sqlite_session(self, db):
        """SQLite 실 세션 → 비-PG 는 RLS 개념 없음 → connection_bypasses_rls=False.

        A real SQLite session (non-PG, no RLS concept) → connection_bypasses_rls=False.
        """
        summary = saas_service.rls_coverage_summary(db)
        assert summary["connection_bypasses_rls"] is False

    def test_summary_bypass_true_on_postgresql_bypass_role(self):
        """PG + 접속 role rolbypassrls/rolsuper → connection_bypasses_rls=True.

        FORCE 11/11 이어도 BYPASSRLS 접속이면 2차 안전망 미실효 — 거짓 안심 창 가시화
        (운영 postgres 접속 = Phase 4 전환 전 상태).
        PG with a BYPASSRLS/superuser connection role → connection_bypasses_rls=True,
        even when force_applied=True (surfaces the pre-Phase-4 false-confidence window).
        """
        summary = saas_service.rls_coverage_summary(self._pg_mock(11, bypasses=True))
        assert summary["force_applied"] is True
        assert summary["connection_bypasses_rls"] is True

    def test_summary_bypass_false_on_postgresql_app_role(self):
        """PG + 비-BYPASSRLS 앱 role (Phase 4 목표 상태) → connection_bypasses_rls=False.

        PG with the non-BYPASSRLS app role (the Phase 4 target) → False — the warning
        banner must disappear only in this state.
        """
        summary = saas_service.rls_coverage_summary(self._pg_mock(11, bypasses=False))
        assert summary["force_applied"] is True
        assert summary["connection_bypasses_rls"] is False

    def test_summary_force_query_uses_bound_parameters(self):
        """PG 실측 SQL 은 테이블명을 bound parameter 로 전달 의무 (f-string 조립 금지).

        The PG live-check SQL must pass table names as bound parameters —
        no f-string assembly (PR #516 RLS f-string SQL injection 전례 / precedent).

        참고: 정확한 단언 형태는 구현 후 조정 가능 — "테이블명 리스트가 파라미터로 전달"
        수준의 행동 단언만 고정한다.
        Note: the exact assertion shape may be tuned post-implementation — only the
        behavior "table names travel as parameters" is pinned here.
        """
        matrix_tables = {entry["table"] for entry in _RLS_MATRIX}
        mock_db = self._pg_mock(11)
        saas_service.rls_coverage_summary(mock_db)

        assert mock_db.execute.called, (
            "PG 경로에서 실측 쿼리 미실행 / live-check query was not executed"
        )
        # summary 호출은 force 실측 + bypass 실측 두 쿼리를 실행 — call_args(마지막 호출)
        # 대신 relforcerowsecurity 쿼리를 call_args_list 에서 직접 선별한다 (순서 독립).
        # One summary call runs both the force and the bypass queries — select the
        # relforcerowsecurity call from call_args_list (order-independent) instead of
        # relying on call_args (the last call).
        force_calls = [
            c for c in mock_db.execute.call_args_list
            if c.args and "relforcerowsecurity" in str(c.args[0])
        ]
        assert len(force_calls) == 1, (
            f"relforcerowsecurity 실측 쿼리 1회 기대, 실제 {len(force_calls)}회 / "
            "expected exactly one force live-check query"
        )
        call = force_calls[0]
        sql_text = str(call.args[0])
        for table in matrix_tables:
            # SQL 본문에 테이블명 직접 조립 금지 (f-string SQL injection 전례 차단)
            # Table names must not be assembled into the SQL text (injection precedent)
            assert table not in sql_text, (
                f"SQL 본문에 테이블명 {table!r} 직접 조립 — bound parameter 의무 / "
                "table name assembled into SQL text — must use bound parameters"
            )
        # 테이블명 리스트는 execute 의 파라미터 (positional/keyword) 로 전달돼야 한다
        # The table-name list must travel via execute parameters (positional/keyword)
        params_repr = repr(call.args[1:]) + repr(call.kwargs)
        for table in matrix_tables:
            assert table in params_repr, (
                f"테이블명 {table!r} 이 파라미터로 전달되지 않음 / "
                "table name was not passed as a bound parameter"
            )
