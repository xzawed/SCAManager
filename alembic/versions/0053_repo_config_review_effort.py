"""repo_configs.review_effort — 리포마다 고르는 리뷰 effort 열

repo_configs.review_effort — the per-repo review effort column.

Revision ID: 0053
Revises: 0052

사용자 11-22 «A안을 승인합니다.»(#1905) — 리포 설정 «고급» 의 리뷰 모델 선택 옆에서 effort(low · medium · high)를 고른다.
NULL = 운영 변수 `CLAUDE_CALL_EFFORT`(기본 high) — 기존 행은 NULL 이라 지금 동작 그대로다.
🔴 관측 역할(0049)은 컬럼 단위 GRANT 라 새 컬럼이 저절로 보이지 않는다 — 비밀값이 아닌 설정 값이라 이 revision 이 그 컬럼
하나를 GRANT 한다(0051 과 같은 원칙 · 역할이 없거나 권한이 모자라면 경고만 하고 넘어간다).
User decision 11-22 (A): pick the review effort per repo. NULL falls back to CLAUDE_CALL_EFFORT (default high), so
existing rows keep today's behaviour. The observer role is granted the new non-secret column, as in 0051.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

ROLE = "scamanager_observer"

# 이 revision 이 관측 역할에 더 주는 컬럼 — 0049 `_ALLOWED` · 0051 과 합친 것이 관측 역할이 읽는 전부다.
# Columns this revision adds to the observer allowlist; with 0049 `_ALLOWED` and 0051 this is everything it reads.
_ADDED_GRANTS = {"repo_configs": ("review_effort",)}


def upgrade() -> None:
    op.add_column("repo_configs", sa.Column("review_effort", sa.String(10), nullable=True))
    if not is_postgresql(op.get_bind()):
        return  # SQLite 단위 테스트 — 역할 · 권한이 없다 / SQLite unit tests have no roles
    grants = "\n        ".join(
        f"GRANT SELECT ({', '.join(columns)}) ON {table} TO {ROLE};" for table, columns in _ADDED_GRANTS.items()
    )
    op.execute(f"""
    DO $observer$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE}') THEN
            {grants}
        END IF;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE WARNING '{ROLE}: review_effort not granted (insufficient privilege): %', SQLERRM;
    END
    $observer$;
    """)


def downgrade() -> None:
    # 컬럼을 지우면 그 컬럼 권한도 함께 사라진다 / dropping the column drops its column privileges too
    op.drop_column("repo_configs", "review_effort")
