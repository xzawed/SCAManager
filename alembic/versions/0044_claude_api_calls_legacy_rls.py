"""claude_api_calls RLS 정책 — legacy repo(user_id IS NULL) 포함 (0026 컨벤션 정합)

claude_api_calls RLS policy — include legacy repos (user_id IS NULL), matching the 0026 convention.

Revision ID: 0044
Revises: 0043

0043 정책의 repo 서브쿼리가 `WHERE user_id = app.user_id` 만이라, Phase 4(app-role, 비-BYPASSRLS)
대시보드 읽기에서 legacy repo(user_id IS NULL) 비용 행이 RLS 로 필터링돼 월비용 KPI 에서 누락됐다
(Codex mutual 적발). analyses/merge_attempts 정책(0026)은 이미 `WHERE user_id IS NULL OR
user_id = app.user_id` 로 legacy 를 포함하므로, 동일 대시보드 owner 시맨틱 정합을 위해
claude_api_calls 정책의 repo 서브쿼리에도 `user_id IS NULL` 을 추가한다
(app-layer `claude_api_cost_repo._owned_repo_ids_subquery` legacy 포함 수정과 페어).
The 0043 repo subquery only allowed `WHERE user_id = app.user_id`, so under Phase 4 app-role RLS,
legacy-repo (user_id IS NULL) cost rows were filtered out of the monthly-cost KPI (found by Codex
mutual review). The analyses/merge_attempts policies (0026) already include `user_id IS NULL`, so we
align the claude_api_calls repo subquery to the same convention (pairs with the app-layer fix).
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

# legacy(user_id IS NULL) 포함 — 0026 analyses/merge 컨벤션 정합
# Includes legacy (user_id IS NULL) — matches the 0026 analyses/merge convention
_POLICY_WITH_LEGACY = """
    CREATE POLICY claude_api_calls_user_isolation ON claude_api_calls
        FOR ALL
        USING (
            (user_id IS NULL AND repo_id IS NULL)
            OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
            OR repo_id IN (
                SELECT id FROM repositories
                WHERE user_id IS NULL
                   OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
            )
        );
"""

# 0043 원본(legacy 미포함) — downgrade 복원용
# Original 0043 policy (no legacy) — for downgrade restore
_POLICY_STRICT = """
    CREATE POLICY claude_api_calls_user_isolation ON claude_api_calls
        FOR ALL
        USING (
            (user_id IS NULL AND repo_id IS NULL)
            OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
            OR repo_id IN (
                SELECT id FROM repositories
                WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::integer
            )
        );
"""


def upgrade() -> None:
    # PG 전용 — SQLite 단위 테스트는 RLS 미지원이라 no-op.
    # PostgreSQL only — SQLite unit tests do not support RLS, so this is a no-op.
    if not is_postgresql(op.get_bind()):
        return
    op.execute("DROP POLICY IF EXISTS claude_api_calls_user_isolation ON claude_api_calls;")
    op.execute(_POLICY_WITH_LEGACY)


def downgrade() -> None:
    if not is_postgresql(op.get_bind()):
        return
    op.execute("DROP POLICY IF EXISTS claude_api_calls_user_isolation ON claude_api_calls;")
    op.execute(_POLICY_STRICT)
