"""add auto_merge column to repo_configs

Revision ID: 0004addautomerge
Revises: 0003dropanalysisrules
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = '0004addautomerge'
down_revision = '0003dropanalysisrules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'repo_configs',
        sa.Column('auto_merge', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    op.drop_column('repo_configs', 'auto_merge')
