"""add merge_retry_queue table for CI-aware auto-merge retry (Phase 12)

Revision ID: 0020mergeretryqueue
Revises: 0019leaderboardoptin
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0020mergeretryqueue'
down_revision = '0019leaderboardoptin'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # merge_retry_queue 테이블 생성 — CI-aware auto-merge 재시도 큐
    # Create merge_retry_queue table — CI-aware auto-merge retry queue.
    op.create_table(
        'merge_retry_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('repo_full_name', sa.String(), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column(
            'analysis_id',
            sa.Integer(),
            sa.ForeignKey('analyses.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('commit_sha', sa.String(40), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('threshold_at_enqueue', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('attempts_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('next_retry_at', sa.DateTime(), nullable=False),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('claimed_at', sa.DateTime(), nullable=True),
        sa.Column('claim_token', sa.String(36), nullable=True),
        sa.Column('last_failure_reason', sa.String(), nullable=True),
        sa.Column('last_detail_message', sa.Text(), nullable=True),
        sa.Column('notify_chat_id', sa.String(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    # sweep 인덱스 — (status, next_retry_at) 조합으로 미처리 행 스캔 최적화
    # Sweep index — optimizes scanning for unprocessed rows by (status, next_retry_at).
    op.create_index(
        'ix_merge_retry_queue_sweep',
        'merge_retry_queue',
        ['status', 'next_retry_at'],
    )

    # SHA 조회 인덱스 — 특정 커밋의 큐 상태 빠른 조회
    # SHA lookup index — fast lookup of queue status for a specific commit.
    op.create_index(
        'ix_merge_retry_queue_sha_lookup',
        'merge_retry_queue',
        ['repo_full_name', 'commit_sha', 'status'],
    )

    # 부분 유일 인덱스 — WHERE status = 'pending' 로 활성 행 중복 방지
    # Partial unique index — prevents duplicate active (pending) rows per (repo, PR, SHA).
    # op.create_index 는 WHERE 절 이식성 미지원 → op.execute() 직접 DDL 사용
    # op.create_index does not support WHERE clause portably → use op.execute() for raw DDL.
    op.execute("""
        CREATE UNIQUE INDEX uq_merge_retry_queue_active
            ON merge_retry_queue(repo_full_name, pr_number, commit_sha)
            WHERE status = 'pending'
    """)


def downgrade() -> None:
    # 부분 유일 인덱스 먼저 제거 (일반 인덱스 전에 제거)
    # Drop the partial unique index first (before regular indexes).
    op.execute("DROP INDEX IF EXISTS uq_merge_retry_queue_active")

    # 일반 인덱스 제거
    # Drop regular indexes.
    op.drop_index('ix_merge_retry_queue_sha_lookup', table_name='merge_retry_queue')
    op.drop_index('ix_merge_retry_queue_sweep', table_name='merge_retry_queue')

    # 테이블 제거
    # Drop the table.
    op.drop_table('merge_retry_queue')
