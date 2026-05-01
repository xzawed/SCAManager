"""add ON DELETE CASCADE to gate_decisions.analysis_id (Phase H Critical C7)

12-에이전트 감사 (2026-04-30) Critical C7 — 0002 의 `gate_decisions.analysis_id`
FK 가 ondelete 미설정. Repository → Analysis 삭제 시 GateDecision 행이 고아
또는 FK violation. 다른 모델 (MergeAttempt/MergeRetryQueue/AnalysisFeedback) 은
이미 CASCADE — 일관성 확보.

PostgreSQL: DROP CONSTRAINT + CREATE CONSTRAINT (online, lock 최소화).
SQLite: FK enforcement 가 PRAGMA foreign_keys 의존이라 마이그레이션 무의미 —
운영 DB 는 Postgres 기준이므로 SQLite 분기에서 skip.

Revision ID: 0024gatedecisionscascade
Revises: 0023compositeindexes
Create Date: 2026-05-01
"""
from alembic import op


revision = '0024gatedecisionscascade'
down_revision = '0023compositeindexes'
branch_labels = None
depends_on = None

# 0002 가 명시한 FK 이름 — Postgres 의 기본 명명 규칙 (table_column_fkey)
# Default Postgres FK name from 0002 (table_column_fkey convention)
_FK_NAME = 'gate_decisions_analysis_id_fkey'


def upgrade() -> None:
    # SQLite 는 ALTER TABLE 로 FK 변경 불가 + foreign_keys PRAGMA off 시 검증 안 함.
    # 운영 DB (Postgres) 만 처리. 단위 테스트는 ORM Base.metadata.create_all 로
    # 신규 ondelete='CASCADE' 가 자동 적용됨.
    # SQLite cannot ALTER FKs and skips enforcement by default — production
    # is Postgres so we only act there. Tests get the new ondelete via ORM.
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    op.drop_constraint(_FK_NAME, 'gate_decisions', type_='foreignkey')
    op.create_foreign_key(
        _FK_NAME,
        'gate_decisions',
        'analyses',
        ['analysis_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return

    op.drop_constraint(_FK_NAME, 'gate_decisions', type_='foreignkey')
    op.create_foreign_key(
        _FK_NAME,
        'gate_decisions',
        'analyses',
        ['analysis_id'],
        ['id'],
    )
