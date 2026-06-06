"""issue_registrations RLS policy — PostgreSQL only (정합성 감사 P1).

issue_registrations RLS policy — PostgreSQL only (integrity-audit P1).

Revision ID: 0037
Revises: 0036
Create Date: 2026-06-06

정합성 감사 발견: issue_registrations 는 11개 앱 테이블 중 유일하게 DB-레벨 RLS 2차 격리
안전망이 없었다 (1차 = 앱 레벨 필터). 0029 의 repo_configs/gate_decisions 간접 격리 패턴을
계승하되 issue_registrations 는 repo_id 컬럼을 직접 보유하므로 1-hop 격리를 적용한다.

Integrity-audit finding: issue_registrations was the only one of 11 app tables without a
DB-level RLS 2nd-tier guard (app-level filter is the 1st). Mirrors the 0029 indirect-isolation
pattern but uses 1-hop (issue_registrations has a repo_id column).

legacy NULL 호환: user_id IS NULL 행 허용 (repositories RLS 정합 — 0026/0029 패턴 페어).
legacy NULL compat: allow user_id IS NULL rows (pairs with repositories RLS — 0026/0029).

회귀 가드: tests/unit/migrations/test_0037_issue_registrations_rls.py
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql


revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


# issue_registrations — 간접 1-hop (repo_id → repositories.user_id)
# issue_registrations — indirect 1-hop (repo_id → repositories.user_id)
_RLS_ISSUE_REGISTRATIONS = """
ALTER TABLE issue_registrations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS issue_registrations_user_isolation ON issue_registrations;

CREATE POLICY issue_registrations_user_isolation ON issue_registrations
    FOR ALL
    USING (
        repo_id IN (
            SELECT id FROM repositories
            WHERE user_id IS NULL
               OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
        )
    );
"""


_DROP_ISSUE_REGISTRATIONS = (
    "DROP POLICY IF EXISTS issue_registrations_user_isolation ON issue_registrations; "
    "ALTER TABLE issue_registrations DISABLE ROW LEVEL SECURITY;"
)


def upgrade() -> None:
    """issue_registrations 에 RLS policy 적용 (PostgreSQL 만).

    Apply the RLS policy to issue_registrations (PostgreSQL only).
    SQLite 단위 테스트 환경에서는 자동 skip.
    """
    bind = op.get_bind()
    if not is_postgresql(bind):
        return  # SQLite 단위 테스트 호환 — RLS skip
    op.execute(_RLS_ISSUE_REGISTRATIONS)


def downgrade() -> None:
    """RLS policy 제거 + RLS 비활성 (PostgreSQL 만).

    Drop the RLS policy + disable RLS (PostgreSQL only).
    """
    bind = op.get_bind()
    if not is_postgresql(bind):
        return
    op.execute(_DROP_ISSUE_REGISTRATIONS)
