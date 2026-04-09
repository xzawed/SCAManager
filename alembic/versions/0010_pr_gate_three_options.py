"""PR Gate 3-옵션 분리 — approve_mode, pr_review_comment, merge_threshold

Revision ID: 0010prgatethree
Revises: 0009addhooktoken
Create Date: 2026-04-10
"""
from alembic import op
import sqlalchemy as sa

revision = '0010prgatethree'
down_revision = '0009addhooktoken'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('repo_configs', 'gate_mode', new_column_name='approve_mode')
    op.alter_column('repo_configs', 'auto_approve_threshold', new_column_name='approve_threshold')
    op.alter_column('repo_configs', 'auto_reject_threshold', new_column_name='reject_threshold')
    op.add_column('repo_configs', sa.Column(
        'pr_review_comment', sa.Boolean(), nullable=False, server_default='true'
    ))
    op.add_column('repo_configs', sa.Column(
        'merge_threshold', sa.Integer(), nullable=False, server_default='75'
    ))


def downgrade() -> None:
    op.drop_column('repo_configs', 'merge_threshold')
    op.drop_column('repo_configs', 'pr_review_comment')
    op.alter_column('repo_configs', 'reject_threshold', new_column_name='auto_reject_threshold')
    op.alter_column('repo_configs', 'approve_threshold', new_column_name='auto_approve_threshold')
    op.alter_column('repo_configs', 'approve_mode', new_column_name='gate_mode')
