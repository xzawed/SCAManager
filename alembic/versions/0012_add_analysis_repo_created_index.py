"""Phase 3-B — analyses(repo_id, created_at) 복합 인덱스 추가.

run_analysis_pipeline의 회귀 감지 쿼리가 `repo_id` 필터 + `created_at DESC LIMIT 5`
패턴으로 매 push마다 실행되므로 full scan을 방지하기 위한 인덱스.

Revision ID: 0012regidx
Revises: 0011pushworkflow
Create Date: 2026-04-17
"""
from alembic import op


revision = '0012regidx'
down_revision = '0011pushworkflow'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_analyses_repo_created",
        "analyses",
        ["repo_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_analyses_repo_created", table_name="analyses")
