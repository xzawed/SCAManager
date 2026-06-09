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
# 🔴 regular `import X.Y` 문법 필수 — `importlib.import_module` 은 `src` 를 호출자 globals 에 바인딩하지 않음.
# 🔴 Must use `import X.Y` syntax — importlib.import_module does NOT bind `src` in caller globals,
#    and coverage.py in Python 3.12 rewrites lazy `from X import Y` inside functions to `X.Y` form,
#    which then fails with NameError if `X` is not in scope.
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


def test_repo_id_no_duplicate_ghost_index(engine):
    """repo_id 인덱스는 명시 ix_insight_cache_repo_id 단일 — 중복/유령 인덱스 부재 (#17).

    repo_id index is the single explicit ix_insight_cache_repo_id — no duplicate ghost (#17).

    과거 `Column(..., index=True)` 가 자동명 ix_insight_narrative_cache_repo_id 를 추가 생성해
    SQLite create_all 에만 존재하고 운영 PG(alembic 0031)에는 없는 유령/중복 인덱스가 됐다.
    index=True 제거로 명시 Index 만 남겨 ORM↔alembic 정합을 회복했음을 회귀 가드한다.
    Previously `Column(..., index=True)` created an auto-named ghost index absent from production PG.
    """
    insp = inspect(engine)
    indexes = insp.get_indexes("insight_narrative_cache")
    repo_id_indexes = [ix for ix in indexes if ix["column_names"] == ["repo_id"]]
    # repo_id 단일 컬럼 인덱스는 정확히 1개 (명시 ix_insight_cache_repo_id)
    # Exactly one single-column repo_id index (the explicit ix_insight_cache_repo_id)
    assert len(repo_id_indexes) == 1, (
        f"repo_id 단일 컬럼 인덱스가 {len(repo_id_indexes)}개 — "
        "중복/유령 인덱스(index=True 재도입?) 의심"
    )
    assert repo_id_indexes[0]["name"] == "ix_insight_cache_repo_id"
    # 자동명 유령 인덱스가 부재해야 함
    # The auto-named ghost index must be absent
    names = {ix["name"] for ix in indexes}
    assert "ix_insight_narrative_cache_repo_id" not in names


def test_global_and_repo_rows_coexist(engine):
    """같은 (user_id, days) 에 repo_id=NULL 과 repo_id=N 행이 공존 가능하다."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy.orm import Session

    _now = datetime.now(timezone.utc)
    with Session(engine) as db:
        db.add(src.models.insight_narrative_cache.InsightNarrativeCache(
            user_id=1, days=30, language="en", repo_id=None,
            response_json={"status": "global"}, created_at=_now,
            expires_at=_now + timedelta(hours=1),
        ))
        db.add(src.models.insight_narrative_cache.InsightNarrativeCache(
            user_id=1, days=30, language="en", repo_id=5,
            response_json={"status": "repo"}, created_at=_now,
            expires_at=_now + timedelta(hours=1),
        ))
        db.commit()
        count = db.query(src.models.insight_narrative_cache.InsightNarrativeCache).filter(
            src.models.insight_narrative_cache.InsightNarrativeCache.user_id == 1,
            src.models.insight_narrative_cache.InsightNarrativeCache.days == 30,
        ).count()
        assert count == 2
