"""0031 마이그레이션 회귀 가드 — insight_narrative_cache.repo_id 컬럼 + 인덱스.

0031 migration regression guard — insight_narrative_cache.repo_id column + index.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

# pylint: disable=wrong-import-position
import pytest
from sqlalchemy import create_engine, inspect

from src.database import Base

# Base.metadata.create_all 전 명시 import 의무 — FK 참조 테이블 포함
# Explicit imports required before create_all — including FK-referenced tables
import src.models.user  # noqa: F401  pylint: disable=unused-import,wrong-import-position
import src.models.repository  # noqa: F401  pylint: disable=unused-import,wrong-import-position
import src.models.insight_narrative_cache  # noqa: F401  pylint: disable=unused-import,wrong-import-position


@pytest.fixture()
def engine():
    """In-memory SQLite engine (Base.metadata.create_all 사용)."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_repo_id_column_exists(engine):
    """insight_narrative_cache 테이블에 repo_id 컬럼이 존재한다."""
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("insight_narrative_cache")}
    assert "repo_id" in cols


def test_repo_id_is_nullable(engine):
    """repo_id 컬럼은 nullable 이다 (기존 전체 대시보드 캐시 하위 호환)."""
    insp = inspect(engine)
    col = next(c for c in insp.get_columns("insight_narrative_cache") if c["name"] == "repo_id")
    assert col["nullable"] is True


def test_global_and_repo_rows_coexist(engine):
    """같은 (user_id, days) 에 repo_id=NULL 과 repo_id=N 행이 공존 가능하다."""
    from src.models.insight_narrative_cache import InsightNarrativeCache
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.orm import Session

    _now = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(InsightNarrativeCache(
            user_id=1, days=30, language="en", repo_id=None,
            response_json={"status": "global"}, created_at=_now,
            expires_at=_now + timedelta(hours=1),
        ))
        db.add(InsightNarrativeCache(
            user_id=1, days=30, language="en", repo_id=5,
            response_json={"status": "repo"}, created_at=_now,
            expires_at=_now + timedelta(hours=1),
        ))
        db.commit()
        count = db.query(InsightNarrativeCache).filter(
            InsightNarrativeCache.user_id == 1,
            InsightNarrativeCache.days == 30,
        ).count()
        assert count == 2
