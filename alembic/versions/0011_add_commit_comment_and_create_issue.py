"""add commit_comment and create_issue columns to repo_configs

Revision ID: 0011ccandissue
Revises: 0010prgatethree
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = '0011ccandissue'
down_revision = '0010prgatethree'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('repo_configs', sa.Column(
        'commit_comment', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('repo_configs', sa.Column(
        'create_issue', sa.Boolean(), nullable=False, server_default='false'
    ))


def downgrade() -> None:
    op.drop_column('repo_configs', 'create_issue')
    op.drop_column('repo_configs', 'commit_comment')
