"""repo_configs.review_effort — 리포마다 고르는 리뷰 effort 열

repo_configs.review_effort — the per-repo review effort column.

Revision ID: 0053
Revises: 0052

사용자 11-22 «A안을 승인합니다.»(#1905) — 리포 설정 «고급» 의 리뷰 모델 선택 옆에서 effort(low · medium · high)를 고른다.
NULL = 운영 변수 `CLAUDE_CALL_EFFORT`, 그것도 비면 effort 를 보내지 않는다(판의 기본값). 기존 행은 NULL 이라 지금 동작 그대로다.
User decision 11-22 (A): pick the review effort per repo. NULL falls back to CLAUDE_CALL_EFFORT, then to the model's
default, so existing rows keep today's behaviour.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("repo_configs", sa.Column("review_effort", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("repo_configs", "review_effort")
