"""리포별 AI 리뷰 모델 선택 + 분석당 토큰 사용량 추적 컬럼 추가.

Add per-repo review model override + per-analysis token usage tracking columns.

- repo_configs.review_model  — 리포별 Claude 모델 override (NULL = 전역 기본값)
- analyses.review_model      — 이 분석에 사용된 모델 (비용 역산용)
- analyses.input_tokens      — Anthropic API 입력 토큰 수
- analyses.output_tokens     — Anthropic API 출력 토큰 수

Revision ID: 0032reviewmodel
Revises: 0031repoinsights
Create Date: 2026-05-19
"""
import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0032reviewmodel"
down_revision = "0031repoinsights"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # repo_configs — 리포별 모델 override
    # repo_configs — per-repo model override
    op.add_column("repo_configs", sa.Column("review_model", sa.String(50), nullable=True))

    # analyses — 토큰 사용량 + 모델명 추적
    # analyses — token usage + model name tracking
    op.add_column("analyses", sa.Column("review_model", sa.String(50), nullable=True))
    op.add_column("analyses", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("analyses", sa.Column("output_tokens", sa.Integer(), nullable=True))

    # PostgreSQL 전용 인덱스: 월별 토큰 합산 쿼리 성능 개선
    # PostgreSQL-only index: speeds up monthly token aggregation queries
    if is_postgresql(op.get_bind()):
        op.create_index(
            "ix_analyses_repo_id_created_at_tokens",
            "analyses",
            ["repo_id", "created_at"],
            postgresql_where=sa.text("input_tokens IS NOT NULL"),
        )


def downgrade() -> None:
    if is_postgresql(op.get_bind()):
        op.drop_index("ix_analyses_repo_id_created_at_tokens", table_name="analyses")

    op.drop_column("analyses", "output_tokens")
    op.drop_column("analyses", "input_tokens")
    op.drop_column("analyses", "review_model")
    op.drop_column("repo_configs", "review_model")
