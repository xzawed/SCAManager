"""add railway_deploy_alerts, railway_webhook_token, railway_api_token to repo_configs

Revision ID: 0012railwayfields
Revises: 0011ccandissue
Create Date: 2026-04-20
"""
from alembic import op
import sqlalchemy as sa

revision = '0012railwayfields'
down_revision = '0011ccandissue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('repo_configs', sa.Column(
        'railway_deploy_alerts', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('repo_configs', sa.Column(
        'railway_webhook_token', sa.String(64), nullable=True
    ))
    op.add_column('repo_configs', sa.Column(
        'railway_api_token', sa.String(), nullable=True
    ))
    op.create_unique_constraint(
        'uq_repo_config_railway_webhook_token',
        'repo_configs',
        ['railway_webhook_token']
    )


def downgrade() -> None:
    op.drop_constraint('uq_repo_config_railway_webhook_token', 'repo_configs', type_='unique')
    op.drop_column('repo_configs', 'railway_api_token')
    op.drop_column('repo_configs', 'railway_webhook_token')
    op.drop_column('repo_configs', 'railway_deploy_alerts')
