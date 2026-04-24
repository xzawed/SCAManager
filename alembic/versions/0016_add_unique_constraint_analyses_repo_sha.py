"""add unique constraint (repo_id, commit_sha) to analyses (P2)

Revision ID: 0016uniqueanalysissha
Revises: 0015automergeissue
Create Date: 2026-04-24
"""
from alembic import op

revision = "0016uniqueanalysissha"
down_revision = "0015automergeissue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add DB-level unique constraint to prevent duplicate analysis rows on race condition."""
    # Remove duplicate (repo_id, commit_sha) rows keeping the highest id before adding constraint
    op.execute("""
        DELETE FROM analyses
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM analyses
            GROUP BY repo_id, commit_sha
        )
    """)
    op.create_unique_constraint(
        "uq_analyses_repo_sha",
        "analyses",
        ["repo_id", "commit_sha"],
    )


def downgrade() -> None:
    """Drop unique constraint."""
    op.drop_constraint("uq_analyses_repo_sha", "analyses", type_="unique")
