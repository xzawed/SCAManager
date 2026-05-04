"""Cycle 79 PR 1 — SaaS RLS 보강 (5 누락 테이블) — PostgreSQL only.

Revision ID: 0029rls5missing
Revises: 0028insightcache
Create Date: 2026-05-04

5+1 cross-verify (Cycle 78 NEW-P0-1) — RLS 누락 5 테이블 보강 의무:
- users (self-RLS — 본인 행만)
- repo_configs (repo_full_name → repositories 간접 격리)
- gate_decisions (analysis_id → analyses → repositories 간접 격리)
- merge_retry_queue (repo_full_name → repositories 간접 격리)
- analysis_feedbacks (user_id 직접 격리)

5+1 cross-verify (Cycle 78 NEW-P0-1) — RLS-missing 5 tables to harden:
- users (self-RLS — own row only)
- repo_configs (repo_full_name → repositories indirect isolation)
- gate_decisions (analysis_id → analyses → repositories indirect)
- merge_retry_queue (repo_full_name → repositories indirect)
- analysis_feedbacks (user_id direct)

회귀 가드: tests/unit/migrations/test_0029_rls_5_missing_tables.py
- 마이그레이션 SQL 형식 검증 (SQLite skip — PG only)
- 5 테이블 모두 ALTER + POLICY 명시 검증
- legacy NULL 호환 정합 (단위 테스트 호환)
"""
import sqlalchemy as sa  # noqa: F401  # alembic convention
from alembic import op


revision = "0029rls5missing"
down_revision = "0028insightcache"
branch_labels = None
depends_on = None


# ─── 1. users — self-RLS (본인 행만) ────────────────────────────────────
# id = current_setting('app.user_id')::int (NULL 허용 X — PK)
# id = current_setting('app.user_id')::int (no NULL — PK)
_RLS_USERS = """
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS users_self_isolation ON users;

CREATE POLICY users_self_isolation ON users
    FOR ALL
    USING (
        id = NULLIF(current_setting('app.user_id', true), '')::integer
    );
"""


# ─── 2. repo_configs — 간접 (repo_full_name → repositories) ──────────────
# legacy NULL 페어 (repositories RLS 정합)
# legacy NULL pair (matches repositories RLS)
_RLS_REPO_CONFIGS = """
ALTER TABLE repo_configs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS repo_configs_user_isolation ON repo_configs;

CREATE POLICY repo_configs_user_isolation ON repo_configs
    FOR ALL
    USING (
        repo_full_name IN (
            SELECT full_name FROM repositories
            WHERE user_id IS NULL
               OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
        )
    );
"""


# ─── 3. gate_decisions — 간접 (analysis_id → analyses → repositories) ───
# 2-hop 간접 격리 (analyses 의 RLS 와 페어)
# 2-hop indirect isolation (pairs with analyses RLS)
_RLS_GATE_DECISIONS = """
ALTER TABLE gate_decisions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS gate_decisions_user_isolation ON gate_decisions;

CREATE POLICY gate_decisions_user_isolation ON gate_decisions
    FOR ALL
    USING (
        analysis_id IN (
            SELECT a.id FROM analyses a
            JOIN repositories r ON r.id = a.repo_id
            WHERE r.user_id IS NULL
               OR r.user_id = NULLIF(current_setting('app.user_id', true), '')::integer
        )
    );
"""


# ─── 4. merge_retry_queue — 간접 (repo_full_name → repositories) ────────
# repo_full_name 컬럼 기반 (analysis_id 보다 직접 — merge_attempts 패턴 차용)
# repo_full_name based (more direct than analysis_id — matches merge_attempts pattern)
_RLS_MERGE_RETRY_QUEUE = """
ALTER TABLE merge_retry_queue ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS merge_retry_queue_user_isolation ON merge_retry_queue;

CREATE POLICY merge_retry_queue_user_isolation ON merge_retry_queue
    FOR ALL
    USING (
        repo_full_name IN (
            SELECT full_name FROM repositories
            WHERE user_id IS NULL
               OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
        )
    );
"""


# ─── 5. analysis_feedbacks — 직접 (user_id 컬럼) ─────────────────────────
# 사용자 본인 피드백만 (NULL 허용 X — feedback FK NOT NULL)
# Own feedback only (no NULL — feedback FK NOT NULL)
_RLS_ANALYSIS_FEEDBACKS = """
ALTER TABLE analysis_feedbacks ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS analysis_feedbacks_user_isolation ON analysis_feedbacks;

CREATE POLICY analysis_feedbacks_user_isolation ON analysis_feedbacks
    FOR ALL
    USING (
        user_id = NULLIF(current_setting('app.user_id', true), '')::integer
    );
"""


_RLS_STATEMENTS = (
    _RLS_USERS,
    _RLS_REPO_CONFIGS,
    _RLS_GATE_DECISIONS,
    _RLS_MERGE_RETRY_QUEUE,
    _RLS_ANALYSIS_FEEDBACKS,
)


_DROP_STATEMENTS = (
    "DROP POLICY IF EXISTS users_self_isolation ON users; ALTER TABLE users DISABLE ROW LEVEL SECURITY;",
    "DROP POLICY IF EXISTS repo_configs_user_isolation ON repo_configs; ALTER TABLE repo_configs DISABLE ROW LEVEL SECURITY;",
    "DROP POLICY IF EXISTS gate_decisions_user_isolation ON gate_decisions; ALTER TABLE gate_decisions DISABLE ROW LEVEL SECURITY;",
    "DROP POLICY IF EXISTS merge_retry_queue_user_isolation ON merge_retry_queue; ALTER TABLE merge_retry_queue DISABLE ROW LEVEL SECURITY;",
    "DROP POLICY IF EXISTS analysis_feedbacks_user_isolation ON analysis_feedbacks; ALTER TABLE analysis_feedbacks DISABLE ROW LEVEL SECURITY;",
)


def upgrade() -> None:
    """5 누락 테이블에 RLS policy 적용 (PostgreSQL 만).

    Apply RLS policies to 5 RLS-missing tables (PostgreSQL only).
    SQLite 단위 테스트 환경에서는 자동 skip.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite 단위 테스트 호환 — RLS skip
    for stmt in _RLS_STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    """RLS policy 제거 + RLS 비활성 (PostgreSQL 만).

    Drop RLS policies + disable RLS (PostgreSQL only).
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for stmt in _DROP_STATEMENTS:
        op.execute(stmt)
