"""issue_registrations 테이블 신설 — AI 분석 결과 GitHub Issue 등록 이력.
Create issue_registrations table for AI analysis result GitHub Issue registration history.

Revision ID: 0035
Revises: 0034
Create Date: 2026-05-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issue_registrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("repo_id", sa.Integer(), nullable=False),
        sa.Column("issue_type", sa.String(), nullable=False),
        sa.Column("issue_key", sa.String(length=64), nullable=False),
        sa.Column("github_issue_number", sa.Integer(), nullable=False),
        sa.Column(
            "github_issue_state",
            sa.String(),
            nullable=False,
            server_default="open",
        ),
        sa.Column("github_issue_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repo_id", "issue_key", name="uq_issue_reg_repo_key"),
    )
    op.create_index("ix_issue_reg_analysis_id", "issue_registrations", ["analysis_id"])
    op.create_index("ix_issue_reg_repo_id", "issue_registrations", ["repo_id"])


def downgrade() -> None:
    op.drop_index("ix_issue_reg_repo_id", table_name="issue_registrations")
    op.drop_index("ix_issue_reg_analysis_id", table_name="issue_registrations")
    op.drop_table("issue_registrations")
