"""repo_config: disabled_tools JSON 컬럼 추가
Add disabled_tools JSON column to repo_config for per-repo tool exclusion.

Revision ID: 0036
Revises: 0035
Create Date: 2026-05-28
"""
import sqlalchemy as sa
from alembic import op

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # JSON 타입 — PostgreSQL(jsonb) + SQLite(TEXT) 양쪽 호환
    # JSON type — compatible with both PostgreSQL (jsonb) and SQLite (TEXT)
    op.add_column(
        'repo_configs',
        sa.Column('disabled_tools', sa.JSON(), nullable=False, server_default='[]'),
    )


def downgrade() -> None:
    op.drop_column('repo_configs', 'disabled_tools')
