"""add hook_token column to repo_configs

Revision ID: 0009addhooktoken
Revises: 0008addcommitmsg
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0009addhooktoken'
down_revision = '0008addcommitmsg'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('repo_configs', sa.Column('hook_token', sa.String(), nullable=True))
    op.create_unique_constraint('uq_repo_configs_hook_token', 'repo_configs', ['hook_token'])


def downgrade() -> None:
    op.drop_constraint('uq_repo_configs_hook_token', 'repo_configs', type_='unique')
    op.drop_column('repo_configs', 'hook_token')
