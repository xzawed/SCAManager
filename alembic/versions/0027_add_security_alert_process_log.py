"""Cycle 73 F1 — SecurityAlertProcessLog table + RLS policy (PostgreSQL only)

Revision ID: 0027securityalertlog
Revises: 0026supabasrlspolicies
Create Date: 2026-05-04

GitHub Code Scanning + Secret Scanning alert 처리 audit log.
GitHub Code Scanning + Secret Scanning alert process audit log.

- alert 별 분류 (Claude AI 권장 vs 사용자 결정) 추적
- RLS policy: repo_id → repositories.user_id 간접 격리 (analyses 패턴 차용)
- 신규 테이블 = legacy NULL 허용 X (Phase 3 RLS 정합 — 신규 데이터만 user_id 명시)

회귀 가드: tests/unit/migrations/test_0027_security_alert_log.py
"""
import sqlalchemy as sa
from alembic import op


revision = "0027securityalertlog"
down_revision = "0026supabasrlspolicies"
branch_labels = None
depends_on = None


# RLS policy SQL — repo_id 간접 격리 (analyses 패턴 차용 — 0026 L60-67)
# RLS policy SQL — repo_id indirect isolation (analyses pattern — 0026 L60-67)
_RLS_SECURITY_ALERT_LOGS = """
ALTER TABLE security_alert_process_logs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS security_alert_logs_isolation ON security_alert_process_logs;
CREATE POLICY security_alert_logs_isolation ON security_alert_process_logs
    USING (
        repo_id IN (
            SELECT id FROM repositories
            WHERE user_id = NULLIF(current_setting('app.user_id', true), '')::integer
        )
    );
"""


def upgrade() -> None:
    """신규 audit log 테이블 + RLS policy.
    Create new audit log table + RLS policy.
    """
    op.create_table(
        "security_alert_process_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "repo_id",
            sa.Integer(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alert_type", sa.String(), nullable=False),  # "code_scanning" | "secret_scanning"
        sa.Column("alert_number", sa.Integer(), nullable=False),  # GitHub alert # (per-repo unique)
        sa.Column("severity", sa.String(), nullable=True),  # critical/high/medium/low/note
        sa.Column("rule_id", sa.String(), nullable=True),  # CodeQL rule ID
        sa.Column("ai_classification", sa.String(), nullable=True),
        # "false_positive" | "used_in_tests" | "actual_violation" | "deferred"
        sa.Column("ai_confidence", sa.Float(), nullable=True),  # 0.0~1.0
        sa.Column("ai_reason", sa.String(), nullable=True),  # 1줄 사유
        sa.Column("user_decision", sa.String(), nullable=True),
        # NULL = pending / "accept_ai" / "override_dismiss" / "override_keep"
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("repo_id", "alert_type", "alert_number", name="uq_security_alert_process_logs"),
    )
    op.create_index(
        op.f("ix_security_alert_process_logs_repo_id"),
        "security_alert_process_logs",
        ["repo_id"],
    )
    op.create_index(
        op.f("ix_security_alert_process_logs_processed_at"),
        "security_alert_process_logs",
        ["processed_at"],
    )

    # PostgreSQL 만 RLS policy 적용 (SQLite 단위 테스트 skip)
    # PostgreSQL only — RLS policy (SQLite unit tests skip)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(_RLS_SECURITY_ALERT_LOGS)


def downgrade() -> None:
    """RLS policy + 테이블 drop.
    Drop RLS policy + table.
    """
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS security_alert_logs_isolation ON security_alert_process_logs;")

    op.drop_index(
        op.f("ix_security_alert_process_logs_processed_at"),
        table_name="security_alert_process_logs",
    )
    op.drop_index(
        op.f("ix_security_alert_process_logs_repo_id"),
        table_name="security_alert_process_logs",
    )
    op.drop_table("security_alert_process_logs")
