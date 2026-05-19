"""InsightNarrativeCache 에러 추적 컬럼 단위 테스트 — 0033 마이그레이션 페어.

Unit tests for record_error / record_error_repo repository helpers (0033 migration pair).

검증 케이스:
  1. record_error — 신규 row 생성 (user_id=N, repo_id=None)
  2. record_error — 기존 row 카운터 증가
  3. record_error — expires_at = now (즉시 만료, 재시도 차단 없음)
  4. record_error — 다른 user_id row 에 영향 없음
  5. record_error — language 파라미터 분리 (en vs ko 별개 row)
  6. record_error_repo — 신규 row 생성 (user_id=N, repo_id=M)
  7. record_error_repo — 기존 row 카운터 증가
  8. record_error_repo — repo_id=None 전체 row 와 충돌 없음
  9. record_error — 성공 캐시 row 존재 시 덮어쓰지 않고 갱신만
 10. record_error_repo — 여러 에러 유형 순차 기록 (type 변경 추적)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis  # noqa: F401  (Base.metadata 등록)
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.repositories import insight_narrative_cache_repo


# ─── Fixture ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션.

    In-memory SQLite session with all ORM tables created.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── record_error (전체 대시보드 — repo_id=None) ──────────────────────────────


def test_record_error_creates_new_row(db):
    """record_error — 기존 row 없을 때 신규 row 생성 확인.

    When no existing row, record_error must insert a new row with:
      - error_count = 1
      - last_error_type = supplied type
      - last_error_at set
      - repo_id = None (dashboard-scoped)
    """
    now = _now()
    insight_narrative_cache_repo.record_error(
        db, user_id=1, days=7, language="en", error_type="api_error", now=now,
    )

    rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 1,
        InsightNarrativeCache.days == 7,
        InsightNarrativeCache.repo_id.is_(None),
    ).all()

    assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
    row = rows[0]
    assert row.error_count == 1
    assert row.last_error_type == "api_error"
    assert row.last_error_at is not None
    assert row.repo_id is None
    assert row.language == "en"


def test_record_error_increments_existing_counter(db):
    """record_error — 기존 row 있을 때 error_count 증가 확인.

    When a row already exists, record_error must increment error_count (not insert new).
    """
    now = _now()
    # 1차 에러 기록
    insight_narrative_cache_repo.record_error(
        db, user_id=2, days=30, language="en", error_type="api_error", now=now,
    )
    # 2차 에러 기록 (동일 키)
    insight_narrative_cache_repo.record_error(
        db, user_id=2, days=30, language="en", error_type="APITimeoutError",
        now=now + timedelta(minutes=5),
    )

    rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 2,
        InsightNarrativeCache.days == 30,
        InsightNarrativeCache.repo_id.is_(None),
    ).all()

    assert len(rows) == 1, f"Expected 1 row (not 2), got {len(rows)}"
    assert rows[0].error_count == 2
    assert rows[0].last_error_type == "APITimeoutError"  # 최신 유형으로 갱신


def test_record_error_expires_at_now(db):
    """record_error — expires_at = now (즉시 만료) 확인.

    The error row must be immediately expired (expires_at <= now)
    so it never blocks a fresh retry attempt.
    """
    now = _now()
    insight_narrative_cache_repo.record_error(
        db, user_id=3, days=7, language="en", error_type="api_error", now=now,
    )

    row = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 3,
        InsightNarrativeCache.days == 7,
        InsightNarrativeCache.repo_id.is_(None),
    ).first()

    assert row is not None
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    # expires_at 는 now 이하여야 함 (즉시 만료)
    assert expires <= now + timedelta(seconds=1), (
        f"expires_at={expires} should be <= now={now} (immediately expired)"
    )


def test_record_error_does_not_affect_other_users(db):
    """record_error — 다른 user_id row 에 영향 없음.

    Recording an error for user_id=4 must not create or modify rows for user_id=5.
    """
    now = _now()
    insight_narrative_cache_repo.record_error(
        db, user_id=4, days=7, language="en", error_type="no_data", now=now,
    )

    # user_id=5 row 없어야 함
    count = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 5,
    ).count()
    assert count == 0, f"Expected 0 rows for user_id=5, got {count}"


def test_record_error_language_isolation(db):
    """record_error — language 파라미터로 다른 row 생성 확인.

    record_error with language='en' and language='ko' must create two separate rows.
    """
    now = _now()
    insight_narrative_cache_repo.record_error(
        db, user_id=6, days=7, language="en", error_type="api_error", now=now,
    )
    insight_narrative_cache_repo.record_error(
        db, user_id=6, days=7, language="ko", error_type="api_error", now=now,
    )

    rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 6,
        InsightNarrativeCache.days == 7,
        InsightNarrativeCache.repo_id.is_(None),
    ).all()

    assert len(rows) == 2, f"Expected 2 language-isolated rows, got {len(rows)}"
    languages = {r.language for r in rows}
    assert languages == {"en", "ko"}


def test_record_error_updates_existing_success_row(db):
    """record_error — 성공 캐시 row 에 에러 정보 갱신 (덮어쓰기 아님).

    When a success-cached row already exists, record_error must update its
    error fields without replacing response_json or resetting expires_at of
    the existing entry (it sets expires_at=now to invalidate it on error-only rows,
    but updates existing rows which may have had a valid expires_at).
    Crucially, the row count remains 1 (no duplicate insert).
    """
    now = _now()
    # 먼저 성공 캐시 row 삽입
    insight_narrative_cache_repo.upsert(
        db, user_id=7, days=7, language="en",
        response={"status": "success", "positive_highlights": ["A"]},
        now=now - timedelta(minutes=30),
    )

    # 에러 발생 기록
    insight_narrative_cache_repo.record_error(
        db, user_id=7, days=7, language="en", error_type="parse_error", now=now,
    )

    rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 7,
        InsightNarrativeCache.days == 7,
        InsightNarrativeCache.repo_id.is_(None),
    ).all()

    # row 중복 없이 1개
    assert len(rows) == 1, f"Expected 1 row (no duplicate insert), got {len(rows)}"
    row = rows[0]
    assert row.error_count == 1
    assert row.last_error_type == "parse_error"
    # response_json 은 기존 success 데이터 보존
    assert row.response_json.get("status") == "success"


# ─── record_error_repo (리포별 — repo_id=M) ───────────────────────────────────


def test_record_error_repo_creates_new_row(db):
    """record_error_repo — repo_id 포함 신규 row 생성 확인.

    record_error_repo must create a row with the correct repo_id != None.
    """
    now = _now()
    insight_narrative_cache_repo.record_error_repo(
        db, user_id=10, repo_id=99, days=7, language="en",
        error_type="api_error", now=now,
    )

    row = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 10,
        InsightNarrativeCache.repo_id == 99,
        InsightNarrativeCache.days == 7,
    ).first()

    assert row is not None
    assert row.repo_id == 99
    assert row.error_count == 1
    assert row.last_error_type == "api_error"


def test_record_error_repo_increments_counter(db):
    """record_error_repo — 두 번 호출 시 error_count 2로 증가.

    Calling record_error_repo twice for the same key must increment error_count to 2.
    """
    now = _now()
    insight_narrative_cache_repo.record_error_repo(
        db, user_id=11, repo_id=100, days=7, language="en",
        error_type="api_error", now=now,
    )
    insight_narrative_cache_repo.record_error_repo(
        db, user_id=11, repo_id=100, days=7, language="en",
        error_type="APIConnectionError", now=now + timedelta(minutes=10),
    )

    rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 11,
        InsightNarrativeCache.repo_id == 100,
        InsightNarrativeCache.days == 7,
    ).all()

    assert len(rows) == 1
    assert rows[0].error_count == 2
    assert rows[0].last_error_type == "APIConnectionError"


def test_record_error_repo_no_conflict_with_dashboard_row(db):
    """record_error_repo — repo_id=None 전체 row 와 충돌 없음.

    A repo-scoped error row (repo_id=99) must coexist with a dashboard-scoped
    error row (repo_id=None) for the same user without collision.
    """
    now = _now()
    # 전체 대시보드 에러
    insight_narrative_cache_repo.record_error(
        db, user_id=12, days=7, language="en", error_type="api_error", now=now,
    )
    # 리포별 에러
    insight_narrative_cache_repo.record_error_repo(
        db, user_id=12, repo_id=200, days=7, language="en",
        error_type="api_error", now=now,
    )

    all_rows = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 12,
        InsightNarrativeCache.days == 7,
    ).all()

    assert len(all_rows) == 2, f"Expected 2 rows (dashboard + repo), got {len(all_rows)}"
    repo_ids = {r.repo_id for r in all_rows}
    assert None in repo_ids, "Expected a dashboard row (repo_id=None)"
    assert 200 in repo_ids, "Expected a repo row (repo_id=200)"


def test_record_error_repo_multiple_error_types(db):
    """record_error_repo — 여러 에러 유형 순차 기록 시 last_error_type 최신 유형 추적.

    Sequential calls with different error types must update last_error_type each time.
    """
    now = _now()
    error_sequence = ["APIStatusError", "APITimeoutError", "InternalServerError"]

    for i, etype in enumerate(error_sequence):
        insight_narrative_cache_repo.record_error_repo(
            db, user_id=13, repo_id=300, days=14, language="en",
            error_type=etype, now=now + timedelta(minutes=i * 5),
        )

    row = db.query(InsightNarrativeCache).filter(
        InsightNarrativeCache.user_id == 13,
        InsightNarrativeCache.repo_id == 300,
        InsightNarrativeCache.days == 14,
    ).first()

    assert row is not None
    assert row.error_count == 3, f"Expected error_count=3, got {row.error_count}"
    assert row.last_error_type == "InternalServerError", (
        f"Expected last_error_type='InternalServerError', got '{row.last_error_type}'"
    )
