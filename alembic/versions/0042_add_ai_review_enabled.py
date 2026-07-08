"""repo_config: ai_review_enabled Boolean 컬럼 추가
Add ai_review_enabled Boolean column to repo_configs for per-repo AI review on/off.

Revision ID: 0042
Revises: 0041
"""
from alembic import op
import sqlalchemy as sa

revision = '0042'
down_revision = '0041'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 리포 전부 활성 유지 — server_default true (NOT NULL 안전)
    # Keep all existing repos enabled — server_default true (NOT NULL safe)
    op.add_column(
        'repo_configs',
        sa.Column('ai_review_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('repo_configs', 'ai_review_enabled')
