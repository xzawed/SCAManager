"""add users table and repositories.user_id FK

Revision ID: 0005addusers
Revises: 0004addautomerge
Create Date: 2026-04-07
"""
from alembic import op
import sqlalchemy as sa

revision = '0005addusers'
down_revision = '0004addautomerge'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('google_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    op.add_column(
        'repositories',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True)
    )
    op.create_index(op.f('ix_repositories_user_id'), 'repositories', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_repositories_user_id'), table_name='repositories')
    op.drop_column('repositories', 'user_id')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
