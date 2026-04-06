"""drop analysis_rules column from repo_configs

Revision ID: 0003dropanalysisrules
Revises: 0002phase3
Create Date: 2026-04-07
"""
from alembic import op

revision = '0003dropanalysisrules'
down_revision = '0002phase3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('repo_configs', 'analysis_rules')


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column('repo_configs', sa.Column('analysis_rules', sa.JSON(), nullable=True))
