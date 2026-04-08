"""add commit_message column to analyses

Revision ID: 0008addcommitmsg
Revises: 0007notifychannels
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0008addcommitmsg'
down_revision = '0007notifychannels'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('analyses', sa.Column('commit_message', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('analyses', 'commit_message')
