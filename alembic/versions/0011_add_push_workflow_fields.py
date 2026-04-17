"""Phase 3 — push workflow 실질화: push_commit_comment, regression_alert,
regression_drop_threshold, block_threshold 컬럼 추가.

Revision ID: 0011pushworkflow
Revises: 0010prgatethree
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = '0011pushworkflow'
down_revision = '0010prgatethree'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('repo_configs', sa.Column(
        'push_commit_comment', sa.Boolean(), nullable=False, server_default='true'
    ))
    op.add_column('repo_configs', sa.Column(
        'regression_alert', sa.Boolean(), nullable=False, server_default='true'
    ))
    op.add_column('repo_configs', sa.Column(
        'regression_drop_threshold', sa.Integer(), nullable=False, server_default='15'
    ))
    op.add_column('repo_configs', sa.Column(
        'block_threshold', sa.Integer(), nullable=True
    ))


def downgrade() -> None:
    op.drop_column('repo_configs', 'block_threshold')
    op.drop_column('repo_configs', 'regression_drop_threshold')
    op.drop_column('repo_configs', 'regression_alert')
    op.drop_column('repo_configs', 'push_commit_comment')
