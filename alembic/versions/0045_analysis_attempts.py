"""analysis_attempts — 진행 중 분석의 흔적 테이블 (파이프라인 소실 탐지)

analysis_attempts — in-flight analysis breadcrumbs (pipeline loss detection).

Revision ID: 0045
Revises: 0044

분석 파이프라인은 in-process BackgroundTask 로 돌고 내구 큐가 없다. webhook 핸들러가 GitHub 에
200 을 선반환한 뒤 파일 수집 + Claude 리뷰(수 분)를 하는데, 유일한 내구 기록인 `analyses` 행은
그 모든 작업이 끝난 뒤 저장된다. 그 창에서 SIGTERM(Railway 재배포)·OOM·크래시가 나면 분석이
조용히 증발하고 "아직 분석 안 됨"과 영영 구별되지 않는다 — 탐지 수단이 0이었다.

이 테이블은 소실을 막지 않는다. 비싼 작업 전에 행을 남기고 정상 종료 시 지우므로,
**남아 있는 오래된 행 = 소실된 분석**이다.

The analysis pipeline runs as an in-process BackgroundTask with no durable queue: the webhook
handler returns 200 to GitHub before file collection + the Claude review (minutes), and the only
durable record — the `analyses` row — lands after all of it. A SIGTERM (Railway redeploy)/OOM/crash
in that window makes the analysis vanish, indistinguishable from "not analyzed yet", with zero
means of detection. This table does not prevent the loss; a row is written before the expensive
work and deleted on normal completion, so a surviving stale row means a lost analysis.

RLS: repo_id 간접 (repositories 페어) — 0026 컨벤션대로 legacy(user_id IS NULL) 포함.
🔴 legacy 절 누락은 0043→0044 에서 실제 사고였다(대시보드 KPI 누락) — 같은 실수 반복 금지.
RLS: indirect via repo_id (repositories pair) — includes legacy (user_id IS NULL) per the 0026
convention. Omitting the legacy clause was a real incident in 0043→0044 (KPI rows filtered out).
"""
import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "analysis_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "repo_id", sa.Integer(),
            sa.ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("commit_sha", sa.String(), nullable=False),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(length=32), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(), nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_analysis_attempts_id", "analysis_attempts", ["id"])
    # orphan 조회(`started_at < cutoff`) 전용 — 이 테이블의 유일한 스캔 패턴.
    # Sole scan pattern — the orphan lookup (`started_at < cutoff`).
    op.create_index("ix_analysis_attempts_started_at", "analysis_attempts", ["started_at"])
    op.create_unique_constraint(
        "uq_analysis_attempts_repo_sha", "analysis_attempts", ["repo_id", "commit_sha"],
    )

    if not is_postgresql(op.get_bind()):
        return
    op.execute("ALTER TABLE analysis_attempts ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE analysis_attempts FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        CREATE POLICY analysis_attempts_user_isolation ON analysis_attempts
            FOR ALL
            USING (
                repo_id IN (
                    SELECT id FROM repositories
                    WHERE user_id IS NULL
                       OR user_id = NULLIF(current_setting('app.user_id', true), '')::integer
                )
            );
        """
    )


def downgrade() -> None:
    if is_postgresql(op.get_bind()):
        op.execute("DROP POLICY IF EXISTS analysis_attempts_user_isolation ON analysis_attempts;")
    op.drop_constraint("uq_analysis_attempts_repo_sha", "analysis_attempts", type_="unique")
    op.drop_index("ix_analysis_attempts_started_at", table_name="analysis_attempts")
    op.drop_index("ix_analysis_attempts_id", table_name="analysis_attempts")
    op.drop_table("analysis_attempts")
