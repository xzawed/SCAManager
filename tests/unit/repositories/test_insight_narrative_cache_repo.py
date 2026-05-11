"""Cycle 74 PR-B Phase 2-B 🅑 — insight_narrative_cache_repo 단위 테스트."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.user import User  # noqa: F401  (register on metadata)
from src.models.insight_narrative_cache import InsightNarrativeCache  # noqa: F401
from src.repositories import insight_narrative_cache_repo


@pytest.fixture
def db() -> Session:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(bind=engine)
    session = Session_()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def test_get_fresh_returns_none_when_absent(db):
    """캐시 없음 → None."""
    result = insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7)
    assert result is None


def test_upsert_then_get_fresh_returns_cached(db):
    """upsert 후 즉시 get_fresh = response_json 반환."""
    response = {"status": "success", "positive_highlights": ["a"], "days": 7}
    insight_narrative_cache_repo.upsert(db, user_id=1, days=7, response=response)
    result = insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7)
    assert result == response


def test_get_fresh_returns_none_after_ttl_expiry(db):
    """TTL 만료 후 get_fresh = None (재생성 의무)."""
    now = datetime.now(timezone.utc)
    insight_narrative_cache_repo.upsert(
        db, user_id=1, days=7, response={"status": "success"},
        ttl_seconds=60, now=now,
    )
    # 61초 후 = 만료
    future = now + timedelta(seconds=61)
    result = insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7, now=future)
    assert result is None


def test_upsert_replaces_existing(db):
    """동일 (user_id, days) 재 upsert = INSERT 가 아닌 UPDATE."""
    insight_narrative_cache_repo.upsert(
        db, user_id=1, days=7, response={"v": 1},
    )
    insight_narrative_cache_repo.upsert(
        db, user_id=1, days=7, response={"v": 2},
    )
    result = insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7)
    assert result == {"v": 2}
    # 단일 row 만 존재
    rows = db.query(InsightNarrativeCache).filter_by(user_id=1, days=7).all()
    assert len(rows) == 1


def test_invalidate_returns_true_when_present(db):
    """invalidate = 존재 시 True + DELETE."""
    insight_narrative_cache_repo.upsert(db, user_id=1, days=7, response={"v": 1})
    deleted = insight_narrative_cache_repo.invalidate(db, user_id=1, days=7)
    assert deleted is True
    assert insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7) is None


def test_invalidate_returns_false_when_absent(db):
    """invalidate = 없음 시 False (no-op)."""
    deleted = insight_narrative_cache_repo.invalidate(db, user_id=1, days=7)
    assert deleted is False


def test_per_user_isolation(db):
    """(user_id, days) 키 격리 — user_id 다르면 독립 캐시."""
    insight_narrative_cache_repo.upsert(db, user_id=1, days=7, response={"u": 1})
    insight_narrative_cache_repo.upsert(db, user_id=2, days=7, response={"u": 2})
    assert insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7) == {"u": 1}
    assert insight_narrative_cache_repo.get_fresh(db, user_id=2, days=7) == {"u": 2}


def test_language_filter_isolates_cache(db):
    """language 파라미터 — ko / en 독립 캐시."""
    insight_narrative_cache_repo.upsert(db, user_id=1, days=7, language="en", response={"lang": "en"})
    insight_narrative_cache_repo.upsert(db, user_id=1, days=7, language="ko", response={"lang": "ko"})
    assert insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7, language="en") == {"lang": "en"}
    assert insight_narrative_cache_repo.get_fresh(db, user_id=1, days=7, language="ko") == {"lang": "ko"}


# ─── repo-scoped helpers (0031) ────────────────────────────────────────────


def test_get_fresh_repo_returns_none_when_absent(db):
    """리포 캐시 없음 → None."""
    result = insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30)
    assert result is None


def test_get_fresh_repo_returns_cached(db):
    """upsert_repo 후 즉시 get_fresh_repo = response_json."""
    insight_narrative_cache_repo.upsert_repo(
        db, user_id=1, repo_id=10, days=30, response={"text": "ok", "status": "success"}
    )
    result = insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30)
    assert result == {"text": "ok", "status": "success"}


def test_get_fresh_repo_returns_none_after_ttl_expiry(db):
    """TTL 만료 후 get_fresh_repo = None."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    insight_narrative_cache_repo.upsert_repo(
        db, user_id=1, repo_id=10, days=30, response={"status": "success"}, ttl_seconds=60, now=now,
    )
    future = now + timedelta(seconds=61)
    assert insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30, now=future) is None


def test_upsert_repo_replaces_existing(db):
    """동일 (user_id, repo_id, days) 재 upsert = UPDATE (INSERT X)."""
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, response={"v": 1})
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, response={"v": 2})
    result = insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30)
    assert result == {"v": 2}
    rows = db.query(InsightNarrativeCache).filter_by(user_id=1, repo_id=10, days=30).all()
    assert len(rows) == 1


def test_upsert_repo_language_isolation(db):
    """(repo_id, language) 분리 — en/ko 독립."""
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, language="en", response={"lang": "en"})
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, language="ko", response={"lang": "ko"})
    assert insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30, language="en") == {"lang": "en"}
    assert insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30, language="ko") == {"lang": "ko"}


def test_invalidate_repo_with_language(db):
    """invalidate_repo(language=) — 특정 언어 행만 삭제 후 count 반환."""
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, language="en", response={"v": 1})
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, language="ko", response={"v": 2})
    deleted = insight_narrative_cache_repo.invalidate_repo(db, user_id=1, repo_id=10, days=30, language="en")
    assert deleted == 1
    assert insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30, language="en") is None
    assert insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=10, days=30, language="ko") is not None


def test_invalidate_repo_all_languages(db):
    """invalidate_repo(language=None) — 모든 언어 변형 일괄 삭제."""
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, language="en", response={"v": 1})
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=10, days=30, language="ko", response={"v": 2})
    deleted = insight_narrative_cache_repo.invalidate_repo(db, user_id=1, repo_id=10, days=30, language=None)
    assert deleted == 2
    rows = db.query(InsightNarrativeCache).filter_by(user_id=1, repo_id=10, days=30).all()
    assert rows == []


def test_invalidate_repo_absent_returns_zero(db):
    """없는 리포 캐시 삭제 → 0 반환."""
    result = insight_narrative_cache_repo.invalidate_repo(db, user_id=1, repo_id=999, days=30)
    assert result == 0


def test_repo_cache_isolated_from_global(db):
    """리포 캐시 ↔ 전체 캐시 완전 분리 (repo_id=NULL vs repo_id=N)."""
    insight_narrative_cache_repo.upsert(db, user_id=1, days=30, response={"scope": "global"})
    insight_narrative_cache_repo.upsert_repo(db, user_id=1, repo_id=5, days=30, response={"scope": "repo"})
    assert insight_narrative_cache_repo.get_fresh(db, user_id=1, days=30) == {"scope": "global"}
    assert insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=5, days=30) == {"scope": "repo"}
    # 전체 캐시 무효화가 리포 캐시에 영향 없음
    insight_narrative_cache_repo.invalidate(db, user_id=1, days=30)
    assert insight_narrative_cache_repo.get_fresh_repo(db, user_id=1, repo_id=5, days=30) == {"scope": "repo"}
