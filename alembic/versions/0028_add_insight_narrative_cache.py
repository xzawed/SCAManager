"""Cycle 74 PR-B (Phase 2-B 🅑) — InsightNarrativeCache table + RLS policy

Revision ID: 0028insightcache
Revises: 0027securityalertlog
Create Date: 2026-05-04

Insight 모드 (`?mode=insight`) 의 Claude AI narrative 응답을 1시간 TTL 로 캐싱.
Cache Insight mode Claude AI narrative responses with 1h TTL.

key = (user_id, days) — 사용자별 + 윈도우 별 격리.
TTL 만료 시 재생성 default (자동 invalidate 미적용 — MVP 단순화).
사용자 명시 Refresh (?refresh=1) 시 강제 재생성.

회귀 가드: tests/unit/migrations/test_0028_insight_narrative_cache.py
"""
import sqlalchemy as sa
from alembic import op


revision = "0028insightcache"
down_revision = "0027securityalertlog"
branch_labels = None
depends_on = None


# RLS policy SQL — user_id 직접 격리 (analyses 와 다른 패턴 — repo_id 무관, 사용자별 cache)
# RLS policy SQL — direct user_id isolation (different from analyses — no repo_id, per-user cache).
_RLS_INSIGHT_CACHE = """
ALTER TABLE insight_narrative_cache ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS insight_cache_isolation ON insight_narrative_cache;
CREATE POLICY insight_cache_isolation ON insight_narrative_cache
    USING (
        user_id = NULLIF(current_setting('app.user_id', true), '')::integer
    );
"""


def upgrade() -> None:
    """신규 캐시 테이블 + RLS policy.
    Create cache table + RLS policy.
    """
    op.create_table(
        "insight_narrative_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("days", sa.Integer(), nullable=False),  # 윈도우 일수 (1/7/30/90)
        sa.Column("response_json", sa.JSON(), nullable=False),
        # 4 카드 narrative + status + generated_at 통합 dict
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "days", name="uq_insight_cache_user_days"),
    )
    op.create_index(
        op.f("ix_insight_narrative_cache_user_id"),
        "insight_narrative_cache",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_insight_narrative_cache_expires_at"),
        "insight_narrative_cache",
        ["expires_at"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(_RLS_INSIGHT_CACHE)


def downgrade() -> None:
    """RLS policy + 테이블 drop.
    Drop RLS policy + table.
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS insight_cache_isolation ON insight_narrative_cache;")

    op.drop_index(
        op.f("ix_insight_narrative_cache_expires_at"),
        table_name="insight_narrative_cache",
    )
    op.drop_index(
        op.f("ix_insight_narrative_cache_user_id"),
        table_name="insight_narrative_cache",
    )
    op.drop_table("insight_narrative_cache")
