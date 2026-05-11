"""insight_narrative_cache에 repo_id FK 추가 — 리포별 AI 내러티브 캐시 지원.

Add repo_id FK to insight_narrative_cache — repo-specific AI narrative cache support.

Revision ID: 0031repoinsights
Revises: 0030i18ncolumns
Create Date: 2026-05-12
"""
import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0031repoinsights"
down_revision = "0030i18ncolumns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """repo_id 컬럼 추가 + PG 부분 유니크 인덱스 교체.

    Add repo_id column + replace PG unique constraints with partial indexes.
    """
    # 1. repo_id 컬럼 추가 (nullable FK, CASCADE)
    # 1. Add nullable repo_id column (FK with CASCADE delete)
    op.add_column(
        "insight_narrative_cache",
        sa.Column(
            "repo_id",
            sa.Integer(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )

    # 2. 기존 제약 교체 (PG only)
    # 2. Replace old constraint + add partial indexes (PG only)
    if is_postgresql(op.get_bind()):
        # 기존 (user_id, days) 유니크 제약 삭제 — repo_id 추가로 전역+리포 다중 행 필요
        # Drop old (user_id, days) unique constraint — needed for global+repo coexistence
        op.drop_constraint("uq_insight_cache_user_days", "insight_narrative_cache")

        # 전역 캐시 부분 유니크 인덱스 (repo_id IS NULL)
        # Partial unique index for global cache rows (repo_id IS NULL)
        op.execute(
            "CREATE UNIQUE INDEX uq_insight_cache_global "
            "ON insight_narrative_cache (user_id, days, language) "
            "WHERE repo_id IS NULL"
        )

        # 리포별 캐시 부분 유니크 인덱스 (repo_id IS NOT NULL)
        # Partial unique index for repo-specific cache rows
        op.execute(
            "CREATE UNIQUE INDEX uq_insight_cache_repo "
            "ON insight_narrative_cache (user_id, days, language, repo_id) "
            "WHERE repo_id IS NOT NULL"
        )

    # 3. repo_id 검색 인덱스 (전체 환경)
    # 3. repo_id lookup index (all environments)
    op.create_index("ix_insight_cache_repo_id", "insight_narrative_cache", ["repo_id"])


def downgrade() -> None:
    """역순 복구 — 인덱스 삭제 → 컬럼 삭제 → 구 제약 복구.

    Reverse: drop indexes → drop column → restore old constraint.
    """
    op.drop_index("ix_insight_cache_repo_id", table_name="insight_narrative_cache")

    if is_postgresql(op.get_bind()):
        op.execute("DROP INDEX IF EXISTS uq_insight_cache_repo")
        op.execute("DROP INDEX IF EXISTS uq_insight_cache_global")
        op.create_unique_constraint(
            "uq_insight_cache_user_days", "insight_narrative_cache", ["user_id", "days"]
        )

    op.drop_column("insight_narrative_cache", "repo_id")
