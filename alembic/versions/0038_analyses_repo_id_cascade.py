"""add ON DELETE CASCADE to analyses.repo_id FK (정합성 감사 P2 #14)

정합성 감사 full(2026-06-08) P2 #14 — `analyses.repo_id` → repositories.id FK 가
ondelete 미설정. repositories → analyses 삭제 사슬에 DB 레벨 안전망 부재.
analyses 의 child 4종(MergeAttempt/MergeRetryQueue/AnalysisFeedback/GateDecision)은
모두 CASCADE — parent 사슬도 일관성 확보. application-level delete_repo_cascade
우회 경로 보완 (DB 레벨이 1차 안전망).

repo_id 는 NOT NULL 이라 SET NULL 불가, RESTRICT 는 delete_repo_cascade 와 충돌 →
CASCADE (db.md FK ondelete 일관성 매트릭스 정합, 사용자 confirm).

PostgreSQL: DROP CONSTRAINT + CREATE CONSTRAINT (online, lock 최소화).
SQLite: FK enforcement 가 PRAGMA foreign_keys 의존이라 ALTER 무의미 —
운영 DB 는 Postgres 기준이므로 SQLite 분기에서 skip (단위 테스트는 ORM
Base.metadata.create_all 로 신규 ondelete='CASCADE' 자동 적용).

add ON DELETE CASCADE to analyses.repo_id FK — see 0024 (gate_decisions) for the
identical pattern. repo_id is NOT NULL so SET NULL is impossible; CASCADE matches
the db.md FK matrix and the user decision.

Revision ID: 0038
Revises: 0037
Create Date: 2026-06-09
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql


revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

# 3b8216565fed 가 생성한 FK 이름 — Postgres 기본 명명 규칙 (table_column_fkey)
# Default Postgres FK name from 3b8216565fed (table_column_fkey convention)
_FK_NAME = "analyses_repo_id_fkey"


def upgrade() -> None:
    # SQLite 는 ALTER TABLE 로 FK 변경 불가 — 운영 DB(Postgres)만 처리.
    # 단위 테스트는 ORM Base.metadata.create_all 로 신규 ondelete='CASCADE' 적용.
    # SQLite cannot ALTER FKs — only act on Postgres; tests get CASCADE via ORM.
    bind = op.get_bind()
    if not is_postgresql(bind):
        return

    op.drop_constraint(_FK_NAME, "analyses", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "analyses",
        "repositories",
        ["repo_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not is_postgresql(bind):
        return

    op.drop_constraint(_FK_NAME, "analyses", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "analyses",
        "repositories",
        ["repo_id"],
        ["id"],
    )
