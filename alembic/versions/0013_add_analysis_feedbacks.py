"""add analysis_feedbacks table (Phase E.3)

Revision ID: 0013feedbacks
Revises: 0012railwayfields
Create Date: 2026-04-23
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0013feedbacks"
down_revision = "0012railwayfields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create analysis_feedbacks table with unique (analysis_id, user_id)."""
    op.create_table(
        "analysis_feedbacks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("thumbs", sa.Integer(), nullable=False),  # +1 (up) | -1 (down)
        sa.Column("comment", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("analysis_id", "user_id", name="uq_feedback_analysis_user"),
    )
    op.create_index(
        op.f("ix_analysis_feedbacks_analysis_id"),
        "analysis_feedbacks",
        ["analysis_id"],
    )
    op.create_index(
        op.f("ix_analysis_feedbacks_user_id"),
        "analysis_feedbacks",
        ["user_id"],
    )


def downgrade() -> None:
    """Drop analysis_feedbacks table."""
    op.drop_index(op.f("ix_analysis_feedbacks_user_id"), table_name="analysis_feedbacks")
    op.drop_index(op.f("ix_analysis_feedbacks_analysis_id"), table_name="analysis_feedbacks")
    op.drop_table("analysis_feedbacks")
