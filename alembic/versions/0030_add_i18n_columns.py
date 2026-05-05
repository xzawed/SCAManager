"""Phase 1 PR-1c (사이클 84) — 다국어 지원 i18n 컬럼 3건 + composite index 갱신

Revision ID: 0030i18ncolumns
Revises: 0029rls5missing
Create Date: 2026-05-05

Phase 1 PR-1c — i18n 다국어 지원 (영어/한국어/일본어) 인프라 DB 영역.

신규 3 컬럼:
1. users.preferred_language (String(5), NOT NULL, server_default="en")
   — 사용자 선호 언어 (User.preferred_language — Phase 2 PR-4 헤더 dropdown 영역)
2. repo_configs.notification_language (String(5), nullable=True)
   — 리포별 알림 언어 override (NULL = 사용자 preferred_language fallback)
3. insight_narrative_cache.language (String(5), NOT NULL, server_default="en")
   — 캐시 키 분리 (composite index (user_id, days, language))

Composite index 갱신:
- 신규: ix_insight_cache_user_days_language (user_id, days, language)
- 동일 사용자 다른 언어 transition 시 잘못된 캐시 hit 차단 (cross-verify 6차 §3.1)

RLS 호환:
- alembic 0026 + 0029 RLS policy 변화 0 (신규 컬럼 = user_id 격리 직교 속성)
- 기존 RLS policy = user_id 기반 격리 유지

backfill 전략:
- server_default 의존 (앱 로직 0 + 모든 환경 호환)
- 기존 행 → DB 단계 자동 default 삽입 (수작업 누락 위험 0)

회귀 가드: tests/unit/migrations/test_0030_add_i18n_columns.py
"""
import sqlalchemy as sa
from alembic import op


revision = "0030i18ncolumns"
down_revision = "0029rls5missing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """3 컬럼 추가 + composite index 갱신.

    Add 3 i18n columns + composite index for cache key separation.
    """
    # 1. users.preferred_language
    # 1. users.preferred_language
    op.add_column(
        "users",
        sa.Column(
            "preferred_language",
            sa.String(5),
            nullable=False,
            server_default="en",
        ),
    )

    # 2. repo_configs.notification_language (override, nullable)
    # 2. repo_configs.notification_language (override, nullable)
    op.add_column(
        "repo_configs",
        sa.Column(
            "notification_language",
            sa.String(5),
            nullable=True,
        ),
    )

    # 3. insight_narrative_cache.language
    # 3. insight_narrative_cache.language
    op.add_column(
        "insight_narrative_cache",
        sa.Column(
            "language",
            sa.String(5),
            nullable=False,
            server_default="en",
        ),
    )

    # 4. composite index (user_id, days, language) — 캐시 키 분리 의무
    # 4. composite index (user_id, days, language) — multilingual cache key separation
    op.create_index(
        "ix_insight_cache_user_days_language",
        "insight_narrative_cache",
        ["user_id", "days", "language"],
    )


def downgrade() -> None:
    """역순 정확 복구 — composite index → 3 컬럼.

    Reverse exact recovery — composite index → 3 columns.
    """
    # 1. composite index 삭제
    # 1. Drop composite index
    op.drop_index(
        "ix_insight_cache_user_days_language",
        table_name="insight_narrative_cache",
    )

    # 2. insight_narrative_cache.language 컬럼 삭제
    # 2. Drop insight_narrative_cache.language
    op.drop_column("insight_narrative_cache", "language")

    # 3. repo_configs.notification_language 컬럼 삭제
    # 3. Drop repo_configs.notification_language
    op.drop_column("repo_configs", "notification_language")

    # 4. users.preferred_language 컬럼 삭제
    # 4. Drop users.preferred_language
    op.drop_column("users", "preferred_language")
