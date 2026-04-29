"""add merge_attempts.state lifecycle columns (Phase 3 PR-B1)

Tier 3 PR-A 후속 — native enable 성공 시 즉시 success=True 로 기록되는
관측 갭 해소. state/enabled_at/merged_at/disabled_at 4 컬럼 추가.

state 값:
  - legacy               : 0022 이전 모든 행 (backfill 기본값)
  - enabled_pending_merge: native enable 성공, GitHub 측 머지 대기
  - actually_merged      : pull_request.closed merged=true webhook 수신
  - disabled_externally  : pull_request.auto_merge_disabled webhook 수신
  - direct_merged        : REST merge_pr() 즉시 성공

PostgreSQL 11+ 에서 server_default 가 metadata-only ADD COLUMN 으로 처리되어
다운타임 ~0초. SQLite (테스트) 는 batch_alter_table 로 table rebuild.

Revision ID: 0022mergeattemptlifecycle
Revises: 0021analysescreatedatindex
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa


revision = '0022mergeattemptlifecycle'
down_revision = '0021analysescreatedatindex'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch_alter_table 로 SQLite/PostgreSQL 양쪽 호환 (CLAUDE.md 규약: 0007 이후
    # 신규 마이그레이션은 op.add_column 직접 사용 권장이지만 SQLite 호환을 위해
    # 이번 4컬럼 추가는 batch 컨텍스트 안에서 server_default 일괄 적용).
    # batch_alter_table for SQLite/PostgreSQL compatibility — server_default ensures
    # all existing rows get backfilled to "legacy" on PostgreSQL too (metadata-only).
    with op.batch_alter_table('merge_attempts') as batch:
        batch.add_column(sa.Column(
            'state', sa.String(),
            nullable=False, server_default='legacy',
        ))
        batch.add_column(sa.Column('enabled_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('merged_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('disabled_at', sa.DateTime(), nullable=True))

    # 대시보드 / 집계가 (state, repo_name) 으로 자주 그룹화 — 인덱스 추가
    # Dashboard/aggregation queries group by (state, repo_name) — add index.
    op.create_index(
        'ix_merge_attempts_state_repo',
        'merge_attempts',
        ['state', 'repo_name'],
    )


def downgrade() -> None:
    op.drop_index('ix_merge_attempts_state_repo', table_name='merge_attempts')
    with op.batch_alter_table('merge_attempts') as batch:
        batch.drop_column('disabled_at')
        batch.drop_column('merged_at')
        batch.drop_column('enabled_at')
        batch.drop_column('state')
