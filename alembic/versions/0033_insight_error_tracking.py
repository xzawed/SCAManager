"""InsightNarrativeCache 에러 추적 컬럼 3개 추가.

Add 3 error-tracking columns to insight_narrative_cache:
  last_error_at   — 마지막 에러 발생 시각 / timestamp of last error
  error_count     — 누적 에러 횟수 / cumulative error count
  last_error_type — 마지막 에러 유형 문자열 / last error type string

Revision ID: 0033insighterror
Revises: 0032reviewmodel
Create Date: 2026-05-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# ─── revision identifiers ──────────────────────────────────────────────────────
revision = "0033insighterror"
down_revision = "0032reviewmodel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from src.shared.alembic_dialect import is_postgresql  # noqa: PLC0415

    bind = op.get_bind()

    op.add_column(
        "insight_narrative_cache",
        sa.Column("last_error_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "insight_narrative_cache",
        sa.Column(
            "error_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "insight_narrative_cache",
        sa.Column("last_error_type", sa.String(100), nullable=True),
    )

    if is_postgresql(bind):
        # PostgreSQL: 인덱스 추가 (에러 빈도 쿼리 최적화)
        # PostgreSQL: add index for error frequency queries
        op.create_index(
            "ix_insight_cache_last_error_at",
            "insight_narrative_cache",
            ["last_error_at"],
        )


def downgrade() -> None:
    from src.shared.alembic_dialect import is_postgresql  # noqa: PLC0415

    bind = op.get_bind()

    if is_postgresql(bind):
        op.drop_index(
            "ix_insight_cache_last_error_at",
            table_name="insight_narrative_cache",
        )

    op.drop_column("insight_narrative_cache", "last_error_type")
    op.drop_column("insight_narrative_cache", "error_count")
    op.drop_column("insight_narrative_cache", "last_error_at")
