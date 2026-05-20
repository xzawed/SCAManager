"""gate_decisions unique constraint on analysis_id

save_gate_decision() 은 분석 당 1건 upsert 로 동작하므로 UNIQUE constraint 필수.
0002 에서 생성된 ix_gate_decisions_analysis_id (non-unique 인덱스) 를 제거하고
UNIQUE constraint (uq_gate_decisions_analysis_id) 로 대체한다.
중복 행이 존재하는 경우 최신 id 를 보존하고 구 중복을 제거한다.

save_gate_decision() operates as a per-analysis upsert, so a UNIQUE constraint
is required. Drops the non-unique index from 0002 and replaces it with a
UNIQUE constraint. Duplicate rows (if any) are pruned, keeping the latest id.

Revision ID: 0034
Revises: 0033insighterror
Create Date: 2026-05-21
"""
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = '0034'
down_revision = '0033insighterror'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite 는 ALTER TABLE 로 UNIQUE constraint 추가 불가 (DDL 제한).
    # 운영 DB (PostgreSQL) 만 처리. 단위 테스트는 ORM Base.metadata.create_all 로
    # unique=True 가 자동 적용됨.
    # SQLite cannot add UNIQUE constraints via ALTER TABLE.
    # Production (PostgreSQL) only. Tests get unique=True from ORM create_all.
    if not is_postgresql(op.get_bind()):
        return

    # 중복 행 제거 — 동일 analysis_id 중 최신 id 만 보존
    # Prune duplicate rows: keep only the row with the highest id per analysis_id
    op.execute("""
        DELETE FROM gate_decisions
        WHERE id NOT IN (
            SELECT MAX(id) FROM gate_decisions GROUP BY analysis_id
        )
    """)

    # 0002 에서 생성된 non-unique 인덱스 제거 (UNIQUE constraint 가 인덱스를 대체)
    # Drop the non-unique index created in 0002 (the UNIQUE constraint creates its own index)
    op.drop_index('ix_gate_decisions_analysis_id', table_name='gate_decisions')

    # UNIQUE constraint 추가
    # Add UNIQUE constraint
    op.create_unique_constraint(
        'uq_gate_decisions_analysis_id',
        'gate_decisions',
        ['analysis_id'],
    )


def downgrade() -> None:
    # SQLite 분기 보존 (upgrade 와 대칭)
    # Mirror the SQLite guard from upgrade
    if not is_postgresql(op.get_bind()):
        return

    op.drop_constraint('uq_gate_decisions_analysis_id', 'gate_decisions', type_='unique')
    op.create_index('ix_gate_decisions_analysis_id', 'gate_decisions', ['analysis_id'], unique=False)
