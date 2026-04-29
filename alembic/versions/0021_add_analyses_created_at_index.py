"""add analyses.created_at index for trend queries (Phase 2)

추세 차트 + analytics_service 의 `ORDER BY created_at DESC LIMIT N` 쿼리가
1만 row 시점부터 풀스캔으로 P95 ~180ms 까지 악화. 인덱스 추가로 인덱스 스캔
전환 → <50ms. PostgreSQL 11+ 는 metadata-only 변경에 가까워 다운타임 ~0.

Trend chart and analytics_service queries on `ORDER BY created_at DESC LIMIT N`
degrade past 10K rows; this index converts them to index scans (~180ms → <50ms).

Revision ID: 0021analysescreatedatindex
Revises: 0020mergeretryqueue
Create Date: 2026-04-29
"""
from alembic import op


revision = '0021analysescreatedatindex'
down_revision = '0020mergeretryqueue'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 인덱스 이름 명시 — 미명시 시 SQLAlchemy 가 자동 생성 (env 마다 다를 수 있음)
    # Explicit index name avoids env-dependent autonames.
    op.create_index(
        'ix_analyses_created_at',
        'analyses',
        ['created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_analyses_created_at', table_name='analyses')
