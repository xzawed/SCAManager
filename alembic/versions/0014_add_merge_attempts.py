"""add merge_attempts table (Phase F.1)

Revision ID: 0014mergeattempts
Revises: 0013feedbacks
Create Date: 2026-04-24
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0014mergeattempts"
down_revision = "0013feedbacks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create merge_attempts table — auto-merge 시도 이력 관측."""
    op.create_table(
        "merge_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repo_name", sa.String(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("failure_reason", sa.String(), nullable=True),
        sa.Column("detail_message", sa.String(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        op.f("ix_merge_attempts_analysis_id"),
        "merge_attempts",
        ["analysis_id"],
    )
    op.create_index(
        op.f("ix_merge_attempts_repo_name"),
        "merge_attempts",
        ["repo_name"],
    )


def downgrade() -> None:
    """Drop merge_attempts table."""
    op.drop_index(op.f("ix_merge_attempts_repo_name"), table_name="merge_attempts")
    op.drop_index(op.f("ix_merge_attempts_analysis_id"), table_name="merge_attempts")
    op.drop_table("merge_attempts")
