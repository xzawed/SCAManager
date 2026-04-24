"""add auto_merge_issue_on_failure to repo_configs (Phase F.3)

Revision ID: 0015automergeissue
Revises: 0014mergeattempts
Create Date: 2026-04-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0015automergeissue"
down_revision = "0014mergeattempts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add auto_merge_issue_on_failure column to repo_configs."""
    op.add_column(
        "repo_configs",
        sa.Column(
            "auto_merge_issue_on_failure",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop auto_merge_issue_on_failure column from repo_configs."""
    op.drop_column("repo_configs", "auto_merge_issue_on_failure")
