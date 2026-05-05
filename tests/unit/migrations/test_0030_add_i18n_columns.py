"""Phase 1 PR-1c (사이클 84) — alembic 0030 i18n 컬럼 3건 + composite index 회귀 가드.

신규 컬럼:
1. users.preferred_language (String(5), NOT NULL, server_default="en")
2. repo_configs.notification_language (String(5), nullable=True)
3. insight_narrative_cache.language (String(5), NOT NULL, server_default="en")

Composite index:
- ix_insight_cache_user_days_language (user_id, days, language)

회귀 가드 영역:
- 컬럼 추가 검증 (type / nullable / default)
- composite index 갱신 검증
- backfill 검증 (server_default 의존 → 기존 사용자 "en" 자동 할당)
- RLS 호환 (정책 변화 0)
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
import pytest
from sqlalchemy import create_engine, inspect, text

from src.database import Base
# 메모리 pytest-fixture-lazy-orm-import-trap.md 페어 — Base.metadata.create_all 전 명시 import 의무
# Memory pytest-fixture-lazy-orm-import-trap.md pair — explicit import before create_all
import src.models.user  # noqa: F401  pylint: disable=unused-import,wrong-import-position
import src.models.repo_config  # noqa: F401  pylint: disable=unused-import,wrong-import-position
import src.models.insight_narrative_cache  # noqa: F401  pylint: disable=unused-import,wrong-import-position


@pytest.fixture
def engine():
    """In-memory SQLite engine (Base.metadata.create_all 사용)."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _column_info(engine_, table: str, column_name: str) -> dict | None:
    """SQLAlchemy Inspector 로 컬럼 정보 조회. 미존재 시 None."""
    inspector = inspect(engine_)
    for col in inspector.get_columns(table):
        if col["name"] == column_name:
            return col
    return None


def _index_columns(engine_, table: str, index_name: str) -> list[str] | None:
    """인덱스의 컬럼 목록 조회. 미존재 시 None."""
    inspector = inspect(engine_)
    for idx in inspector.get_indexes(table):
        if idx["name"] == index_name:
            return idx["column_names"]
    return None


def test_users_preferred_language_column_added(engine):
    """users.preferred_language 컬럼 추가 검증."""
    col = _column_info(engine, "users", "preferred_language")
    assert col is not None, "users.preferred_language 컬럼 미추가"


def test_users_preferred_language_not_nullable(engine):
    """users.preferred_language NOT NULL 의무."""
    col = _column_info(engine, "users", "preferred_language")
    assert col["nullable"] is False, "preferred_language 는 NOT NULL 의무"


def test_repo_configs_notification_language_column_added(engine):
    """repo_configs.notification_language 컬럼 추가 검증."""
    col = _column_info(engine, "repo_configs", "notification_language")
    assert col is not None, "repo_configs.notification_language 컬럼 미추가"


def test_repo_configs_notification_language_nullable(engine):
    """repo_configs.notification_language nullable 의무 (override = NULL fallback)."""
    col = _column_info(engine, "repo_configs", "notification_language")
    assert col["nullable"] is True, "notification_language 는 nullable 의무 (NULL = fallback)"


def test_insight_cache_language_column_added(engine):
    """insight_narrative_cache.language 컬럼 추가 검증."""
    col = _column_info(engine, "insight_narrative_cache", "language")
    assert col is not None, "insight_narrative_cache.language 컬럼 미추가"


def test_insight_cache_language_not_nullable(engine):
    """insight_narrative_cache.language NOT NULL 의무."""
    col = _column_info(engine, "insight_narrative_cache", "language")
    assert col["nullable"] is False, "insight_narrative_cache.language 는 NOT NULL 의무"


def test_insight_cache_composite_index_exists(engine):
    """composite index (user_id, days, language) 존재 + 정확 컬럼 순서."""
    cols = _index_columns(
        engine,
        "insight_narrative_cache",
        "ix_insight_cache_user_days_language",
    )
    assert cols is not None, (
        "composite index ix_insight_cache_user_days_language 미존재"
    )
    assert cols == ["user_id", "days", "language"], (
        f"composite index 컬럼 순서 불일치: {cols}"
    )


def test_users_preferred_language_default_en(engine):
    """server_default='en' 의존 — 신규 사용자 INSERT 시 자동 'en' 할당."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO users (github_id, email, display_name) "
                "VALUES ('test-user-1', 'test1@example.com', 'Test User 1')"
            )
        )
        conn.commit()
        result = conn.execute(
            text(
                "SELECT preferred_language FROM users WHERE github_id = 'test-user-1'"
            )
        ).fetchone()
        assert result[0] == "en", (
            f"preferred_language default 'en' 미적용: {result[0]}"
        )


def test_insight_cache_language_default_en(engine):
    """insight_narrative_cache.language server_default='en' 검증."""
    from datetime import datetime, timezone

    with engine.connect() as conn:
        # 사용자 먼저 생성 (FK 의존)
        conn.execute(
            text(
                "INSERT INTO users (github_id, email, display_name) "
                "VALUES ('test-cache-user', 'cache@example.com', 'Cache User')"
            )
        )
        user_id = conn.execute(
            text("SELECT id FROM users WHERE github_id = 'test-cache-user'")
        ).fetchone()[0]

        # InsightNarrativeCache row 삽입 (language 컬럼 명시 X — server_default 검증)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            text(
                "INSERT INTO insight_narrative_cache "
                "(user_id, days, response_json, created_at, expires_at) "
                f"VALUES ({user_id}, 7, '{{}}', '{now}', '{now}')"
            )
        )
        conn.commit()

        result = conn.execute(
            text(
                f"SELECT language FROM insight_narrative_cache WHERE user_id = {user_id}"
            )
        ).fetchone()
        assert result[0] == "en", (
            f"insight_narrative_cache.language default 'en' 미적용: {result[0]}"
        )


def test_repo_configs_notification_language_nullable_default_none(engine):
    """repo_configs.notification_language 미명시 시 NULL 자동 할당."""
    with engine.connect() as conn:
        conn.execute(
            text(
                "INSERT INTO repo_configs "
                "(repo_full_name, pr_review_comment, approve_mode, "
                "approve_threshold, reject_threshold, auto_merge, merge_threshold, "
                "commit_comment, create_issue, railway_deploy_alerts, "
                "auto_merge_issue_on_failure) "
                "VALUES ('owner/test-repo', 1, 'disabled', 75, 50, 0, 75, 0, 0, 0, 0)"
            )
        )
        conn.commit()
        result = conn.execute(
            text(
                "SELECT notification_language FROM repo_configs "
                "WHERE repo_full_name = 'owner/test-repo'"
            )
        ).fetchone()
        assert result[0] is None, (
            f"notification_language 기본값은 NULL 의무 (override 영역): {result[0]}"
        )
