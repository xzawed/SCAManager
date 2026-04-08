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
    with op.batch_alter_table('repo_configs') as batch_op:
        batch_op.create_unique_constraint('uq_repo_configs_hook_token', ['hook_token'])


def downgrade() -> None:
    with op.batch_alter_table('repo_configs') as batch_op:
        batch_op.drop_constraint('uq_repo_configs_hook_token', type_='unique')
    op.drop_column('repo_configs', 'hook_token')
