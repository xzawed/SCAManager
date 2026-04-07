"""phase8b github oauth — rename google_id to github_id, add github fields, webhook fields

Revision ID: 0006phase8bgithub
Revises: 0005addusers
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = '0006phase8bgithub'
down_revision = '0005addusers'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users: google_id → github_id (batch mode for SQLite compatibility)
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('google_id', new_column_name='github_id')
        batch_op.add_column(sa.Column('github_login', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('github_access_token', sa.String(), nullable=True))

    # repositories: webhook_secret, webhook_id 추가
    op.add_column('repositories', sa.Column('webhook_secret', sa.String(), nullable=True))
    op.add_column('repositories', sa.Column('webhook_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('repositories', 'webhook_id')
    op.drop_column('repositories', 'webhook_secret')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('github_access_token')
        batch_op.drop_column('github_login')
        batch_op.alter_column('github_id', new_column_name='google_id')
