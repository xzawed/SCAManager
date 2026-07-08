"""claude_api_calls — Anthropic 비용 메트릭 테이블 + RLS

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

from src.shared.alembic_dialect import is_postgresql

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "claude_api_calls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="success"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cache_creation_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Float(), nullable=False, server_default="0"),
        sa.Column("repo_id", sa.Integer(), sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("error_type", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_claude_api_calls_created_at", "claude_api_calls", ["created_at"])
    op.create_index("ix_claude_api_calls_user_created", "claude_api_calls", ["user_id", "created_at"])
    op.create_index("ix_claude_api_calls_repo_created", "claude_api_calls", ["repo_id", "created_at"])

    if not is_postgresql(op.get_bind()):
        return
    op.execute("ALTER TABLE claude_api_calls ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE claude_api_calls FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY claude_api_calls_user_isolation ON claude_api_calls
            FOR ALL
            USING (
                (user_id IS NULL AND repo_id IS NULL)
                OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
                OR repo_id IN (
                    SELECT id FROM repositories
                    WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::integer
                )
            );
        """
    )


def downgrade() -> None:
    if is_postgresql(op.get_bind()):
        op.execute("DROP POLICY IF EXISTS claude_api_calls_user_isolation ON claude_api_calls;")
    op.drop_index("ix_claude_api_calls_repo_created", table_name="claude_api_calls")
    op.drop_index("ix_claude_api_calls_user_created", table_name="claude_api_calls")
    op.drop_index("ix_claude_api_calls_created_at", table_name="claude_api_calls")
    op.drop_table("claude_api_calls")
