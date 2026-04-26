"""add repo_configs.leaderboard_opt_in column

Revision ID: 0019leaderboardoptin
Revises: 0018addauthor
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0019leaderboardoptin'
down_revision = '0018addauthor'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # leaderboard_opt_in: 기본 False — 팀 합의 후 명시 옵트인 필요
    # Default False — requires explicit opt-in after team agreement.
    op.add_column(
        'repo_configs',
        sa.Column('leaderboard_opt_in', sa.Boolean(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('repo_configs', 'leaderboard_opt_in')
