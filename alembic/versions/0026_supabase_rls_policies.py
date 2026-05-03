"""Phase 3 PR 5 — Supabase RLS 권한 모델 (PostgreSQL 전용)

Revision ID: 0026supabasrlspolicies
Revises: 0025dropleaderboardoptin
Create Date: 2026-05-04

Phase 3 PR 5 — SaaS 전환 토대. PostgreSQL Row Level Security (RLS) policy 적용:
- repositories: user_id 기반 격리 (legacy NULL 호환)
- analyses: repo_id → repositories.user_id 간접 격리 (subquery)
- merge_attempts: repo_name → repositories.full_name → user_id 간접 격리

세션 컨텍스트 변수: `app.user_id` (`SET LOCAL app.user_id = '<user_id>'` 패턴).
SCAManager 는 Supabase Auth 미사용 (GitHub OAuth) — auth.uid() 미적용.
세션 변수 미설정 시 (NULL) → policy USING 절이 user_id IS NULL 만 허용 (legacy admin 영역).

SQLite (단위 테스트) 분기: op.execute 모두 skip — RLS 미지원 환경 호환.
앱 레벨 filter (`src/services/dashboard_service.py::_apply_*_user_filter`) 가 1차 안전망.
본 RLS policy 는 운영 환경 (Supabase) 의 2차 안전망 (DB 레벨 격리 — 앱 버그 시에도 데이터 누출 차단).

회귀 가드: tests/unit/migrations/test_0026_rls_policies.py (3 테스트).
"""
# Phase 3 PR 5 — Supabase RLS permission model (PostgreSQL only)
# Provides DB-level isolation as a 2nd safety layer; app-level filter
# (src/services/dashboard_service.py::_apply_*_user_filter) is the 1st layer.
from alembic import op


# revision identifiers, used by Alembic.
# Revision identifiers used by Alembic.
revision = '0026supabasrlspolicies'
down_revision = '0025dropleaderboardoptin'
branch_labels = None
depends_on = None


# RLS policy SQL — repositories: user_id 기반 격리 + legacy NULL 허용
# RLS policy SQL — repositories: user_id-based isolation + legacy NULL allowed
_RLS_REPOSITORIES = """
ALTER TABLE repositories ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS repositories_user_isolation ON repositories;

CREATE POLICY repositories_user_isolation ON repositories
    FOR ALL
    USING (
        user_id IS NULL
        OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
    );
"""

# analyses: repo_id 통한 간접 격리 (subquery — repositories RLS 와 페어 동작)
# analyses: indirect isolation via repo_id (subquery — pairs with repositories RLS)
_RLS_ANALYSES = """
ALTER TABLE analyses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS analyses_user_isolation ON analyses;

CREATE POLICY analyses_user_isolation ON analyses
    FOR ALL
    USING (
        repo_id IN (
            SELECT id FROM repositories
            WHERE user_id IS NULL
               OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
        )
    );
"""

# merge_attempts: repo_name → repositories.full_name 간접 격리
# merge_attempts: indirect isolation via repo_name → repositories.full_name
_RLS_MERGE_ATTEMPTS = """
ALTER TABLE merge_attempts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS merge_attempts_user_isolation ON merge_attempts;

CREATE POLICY merge_attempts_user_isolation ON merge_attempts
    FOR ALL
    USING (
        repo_name IN (
            SELECT full_name FROM repositories
            WHERE user_id IS NULL
               OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
        )
    );
"""


def upgrade() -> None:
    """PG 환경에서 3 테이블 RLS 활성화 + policy 생성. SQLite skip."""
    # SQLite 단위 테스트 환경 — RLS 미지원, 모든 op.execute skip.
    # SQLite unit-test environment — RLS unsupported, skip all op.execute.
    if op.get_context().dialect.name != 'postgresql':
        return

    op.execute(_RLS_REPOSITORIES)
    op.execute(_RLS_ANALYSES)
    op.execute(_RLS_MERGE_ATTEMPTS)


def downgrade() -> None:
    """RLS policy 제거 + RLS 비활성화. PG 전용."""
    if op.get_context().dialect.name != 'postgresql':
        return

    op.execute("DROP POLICY IF EXISTS merge_attempts_user_isolation ON merge_attempts;")
    op.execute("ALTER TABLE merge_attempts DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS analyses_user_isolation ON analyses;")
    op.execute("ALTER TABLE analyses DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS repositories_user_isolation ON repositories;")
    op.execute("ALTER TABLE repositories DISABLE ROW LEVEL SECURITY;")
