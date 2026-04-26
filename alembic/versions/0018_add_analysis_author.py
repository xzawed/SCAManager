"""add analyses.author_login column

Revision ID: 0018addauthor
Revises: 0017addtelegramid
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0018addauthor'
down_revision = '0017addusertelegramid'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # author_login: PR = pull_request.user.login, push = head_commit.author.username
    # 신규 레코드만 채움 — backfill 없음 (NULL 허용, 인덱스로 집계 성능 보장)
    # Populated for new records only — no backfill (nullable, index for aggregation performance).
    op.add_column('analyses', sa.Column('author_login', sa.String(), nullable=True))
    op.create_index('ix_analyses_author_login', 'analyses', ['author_login'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_analyses_author_login', table_name='analyses')
    op.drop_column('analyses', 'author_login')
