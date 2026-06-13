"""Cycle 73 F1 — SecurityAlertProcessLog table + RLS policy (PostgreSQL only)

Revision ID: 0027securityalertlog
Revises: 0026supabasrlspolicies
Create Date: 2026-05-04

GitHub Code Scanning + Secret Scanning alert 처리 audit log.
GitHub Code Scanning + Secret Scanning alert process audit log.

- alert 별 분류 (Claude AI 권장 vs 사용자 결정) 추적
- RLS policy: repo_id → repositories.user_id 간접 격리 (analyses 패턴 차용)
- 신규 테이블 = legacy NULL 허용 X (Phase 3 RLS 정합 — 신규 데이터만 user_id 명시)

RLS policy 회귀 가드: tests/unit/migrations/test_0027_rls_intentional_divergence.py
(0027 정책의 owner 격리 골격 + legacy 전역노출 절 의도적 생략을 잠금 — 정합성 감사 U1)
"""
import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql


revision = "0027securityalertlog"
down_revision = "0026supabasrlspolicies"
branch_labels = None
depends_on = None


# RLS policy SQL — repo_id 간접 격리 (analyses 패턴 차용 — 0026 L60-67)
# RLS policy SQL — repo_id indirect isolation (analyses pattern — 0026 L60-67)
#
# 의도적 divergence (정합성 감사 U1, 2026-06-13 재확인): 이 정책은 0026 형제 정책
# analyses 및 merge_attempts 에 있는 legacy 전역 노출 절을 의도적으로 생략한다.
# 신규 audit-log 테이블이라 user_id 가 비어있는 legacy repo 데이터가 없고, legacy
# 보안알림을 전역 노출하지 않는 더 엄격한 격리가 strict multi-tenancy 방향에 정합한다.
# 운영 실측(legacy repo 0건)으로 영향 없음 확인 → 감사 U1 을 false-positive 로 종결.
# 회귀 가드: tests/unit/migrations/test_0027_rls_intentional_divergence.py
# Intentional divergence (integrity-audit U1, re-confirmed 2026-06-13): this policy
# deliberately omits the legacy global-visibility clause that the 0026 sibling policies
# analyses and merge_attempts carry. As a new audit-log table it has no legacy rows with
# an empty user_id, and keeping legacy security alerts non-global is the stricter,
# multi-tenancy-aligned choice. Do not reintroduce that clause without updating the guard
# test above (it would expose legacy security alerts cross-tenant).
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
    if is_postgresql(bind):
        op.execute(_RLS_SECURITY_ALERT_LOGS)


def downgrade() -> None:
    """RLS policy + 테이블 drop.
    Drop RLS policy + table.
    """
    bind = op.get_bind()
    if is_postgresql(bind):
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
