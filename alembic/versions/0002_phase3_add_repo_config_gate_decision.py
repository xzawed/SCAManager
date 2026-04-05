"""phase3: add repo_configs and gate_decisions tables

Revision ID: 0002phase3
Revises: 3b8216565fed
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0002phase3'
down_revision = '3b8216565fed'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'repo_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(), nullable=False),
        sa.Column('gate_mode', sa.String(), nullable=False, server_default='disabled'),
        sa.Column('auto_approve_threshold', sa.Integer(), nullable=False, server_default='75'),
        sa.Column('auto_reject_threshold', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('notify_chat_id', sa.String(), nullable=True),
        sa.Column('n8n_webhook_url', sa.String(), nullable=True),
        sa.Column('analysis_rules', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_repo_configs_id', 'repo_configs', ['id'], unique=False)
    op.create_index('ix_repo_configs_repo_full_name', 'repo_configs', ['repo_full_name'], unique=True)
    op.create_table(
        'gate_decisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analysis_id', sa.Integer(), nullable=False),
        sa.Column('decision', sa.String(), nullable=False),
        sa.Column('mode', sa.String(), nullable=False),
        sa.Column('decided_by', sa.String(), nullable=True),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['analysis_id'], ['analyses.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_gate_decisions_id', 'gate_decisions', ['id'], unique=False)
    op.create_index('ix_gate_decisions_analysis_id', 'gate_decisions', ['analysis_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_gate_decisions_analysis_id', table_name='gate_decisions')
    op.drop_index('ix_gate_decisions_id', table_name='gate_decisions')
    op.drop_table('gate_decisions')
    op.drop_index('ix_repo_configs_repo_full_name', table_name='repo_configs')
    op.drop_index('ix_repo_configs_id', table_name='repo_configs')
    op.drop_table('repo_configs')
