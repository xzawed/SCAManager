"""add notification channel columns to repo_configs

Revision ID: 0007notifychannels
Revises: 0006phase8bgithub
Create Date: 2026-04-08
"""
from alembic import op
import sqlalchemy as sa

revision = '0007notifychannels'
down_revision = '0006phase8bgithub'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('repo_configs', sa.Column('discord_webhook_url', sa.String(), nullable=True))
    op.add_column('repo_configs', sa.Column('slack_webhook_url', sa.String(), nullable=True))
    op.add_column('repo_configs', sa.Column('custom_webhook_url', sa.String(), nullable=True))
    op.add_column('repo_configs', sa.Column('email_recipients', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('repo_configs', 'email_recipients')
    op.drop_column('repo_configs', 'custom_webhook_url')
    op.drop_column('repo_configs', 'slack_webhook_url')
    op.drop_column('repo_configs', 'discord_webhook_url')
