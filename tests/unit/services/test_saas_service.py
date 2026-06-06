"""saas_service — Cycle 79 PR 3a 회귀 가드.

tenant_inventory + rls_audit_matrix + rls_coverage_summary.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.services import saas_service


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
