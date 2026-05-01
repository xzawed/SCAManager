"""add composite indexes for repo-scoped queries (Phase H PR-4A)

12-에이전트 감사 (2026-04-30) High 성능 — `analytics_service` / leaderboard /
author_trend / Phase F.4 dashboard 쿼리가 복합 인덱스 부재로 1만 row 시점부터
풀스캔. 신규 인덱스 3종 추가:

  - ix_analyses_repo_id_created_at — `WHERE repo_id=X ORDER BY created_at DESC`
    (analytics_service.weekly_summary / moving_average / repo_detail 차트)
  - ix_analyses_repo_id_author_login — leaderboard / author_trend
  - ix_merge_attempts_attempted_at — Phase F.4 dashboard 시계열

PostgreSQL `CREATE INDEX` 는 기본 online (테이블 락 없음) — 다운타임 ~0.
Single-column 인덱스(0021 created_at 등) 는 보존 — 전역 추세 쿼리에 여전히 사용.

Revision ID: 0023compositeindexes
Revises: 0022mergeattemptlifecycle
Create Date: 2026-05-01
"""
from alembic import op


revision = '0023compositeindexes'
down_revision = '0022mergeattemptlifecycle'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. analyses (repo_id, created_at) — repo-scoped 시간 순 쿼리 hot path
    # 1. analyses (repo_id, created_at) — hot path for repo-scoped time-ordered queries
    op.create_index(
        'ix_analyses_repo_id_created_at',
        'analyses',
        ['repo_id', 'created_at'],
    )

    # 2. analyses (repo_id, author_login) — leaderboard / author_trend
    # 2. analyses (repo_id, author_login) — leaderboard / author_trend aggregations
    op.create_index(
        'ix_analyses_repo_id_author_login',
        'analyses',
        ['repo_id', 'author_login'],
    )

    # 3. merge_attempts (attempted_at) — Phase F.4 dashboard 시계열
    # 3. merge_attempts (attempted_at) — Phase F.4 dashboard time-series filter
    op.create_index(
        'ix_merge_attempts_attempted_at',
        'merge_attempts',
        ['attempted_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_merge_attempts_attempted_at', table_name='merge_attempts')
    op.drop_index('ix_analyses_repo_id_author_login', table_name='analyses')
    op.drop_index('ix_analyses_repo_id_created_at', table_name='analyses')
