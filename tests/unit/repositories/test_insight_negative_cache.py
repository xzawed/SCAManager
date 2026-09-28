"""내러티브 부정 캐시 — 최근 실패 판정(`recent_error*`)·성공 시 해제·보존 스윕.

Narrative negative cache — the recent-failure predicate, clearing on success, and the purge sweep.

실패 행은 태어날 때 이미 만료(`expires_at = now`)라 성공 캐시로는 재시도를 못 막는다. 45 s 기한에
걸린 직후 새로 고침할 때마다 유료 호출이 또 나갔다. 부정 캐시는 `last_error_at` 으로 판정한다.
Error rows are born expired, so the success cache never blocked a retry: every reload after a
45 s deadline miss started another paid call. The negative cache reads `last_error_at` instead.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.repositories import insight_narrative_cache_repo as repo_mod

_T0 = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션.
    In-memory SQLite session with every ORM table created.
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


def _dash(db, *, now, user_id=1, days=7, language="en", **kw):
    return repo_mod.recent_error(db, user_id=user_id, days=days, language=language, now=now, **kw)


def _repo(db, *, now, user_id=1, repo_id=5, days=30, language="en", **kw):
    return repo_mod.recent_error_repo(
        db, user_id=user_id, repo_id=repo_id, days=days, language=language, now=now, **kw,
    )


# ─── 판정 — 창 · 유형 ─────────────────────────────────────────────────────────


def test_ttl_is_two_minutes():
    """창 길이는 120 초 — 45 s 실패 직후의 새로 고침을 덮는다(아래 경계 테스트가 이 값을 쓴다)."""
    assert repo_mod.NEGATIVE_TTL_SECONDS == 120


def test_no_row_is_no_hit(db):
    assert _dash(db, now=_T0) is None
    assert _repo(db, now=_T0) is None


def test_success_row_with_null_last_error_at_is_no_hit_not_an_exception(db):
    """성공 캐시 행은 `last_error_at` 이 NULL 이다 — 적중도 예외도 아니다."""
    repo_mod.upsert(db, user_id=1, days=7, language="en", response={"status": "success"}, now=_T0)
    repo_mod.upsert_repo(db, user_id=1, repo_id=5, days=30, language="en",
                         response={"text": "t", "status": "success"}, now=_T0)
    row = db.query(InsightNarrativeCache).filter(InsightNarrativeCache.repo_id.is_(None)).one()
    assert row.last_error_at is None  # 전제 확인 / precondition

    assert _dash(db, now=_T0 + timedelta(seconds=5)) is None
    assert _repo(db, now=_T0 + timedelta(seconds=5)) is None


@pytest.mark.parametrize("error_type", ["api_error", "parse_error"])
def test_recent_dashboard_error_is_a_hit_returning_its_type(db, error_type):
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type=error_type, now=_T0)
    assert _dash(db, now=_T0 + timedelta(seconds=10)) == error_type


@pytest.mark.parametrize("error_type", ["APITimeoutError", "TimeoutError", "JSONDecodeError", "max_tokens"])
def test_recent_repo_error_is_a_hit_returning_its_type(db, error_type):
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=30, language="en",
                               error_type=error_type, now=_T0)
    assert _repo(db, now=_T0 + timedelta(seconds=10)) == error_type


def test_no_data_is_never_a_hit(db):
    """`no_data` 는 Claude 를 부르지 않은 기록이다 — 막을 유료 호출이 없고, 데이터가 생기면 바로 불러야 한다."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="no_data", now=_T0)
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=30, language="en",
                               error_type="no_data", now=_T0)
    assert _dash(db, now=_T0 + timedelta(seconds=1)) is None
    assert _repo(db, now=_T0 + timedelta(seconds=1)) is None


def test_null_error_type_with_a_recent_timestamp_is_no_hit(db):
    """유형이 비어 있으면 무엇을 돌려줄지 모른다 — 적중으로 치지 않는다."""
    db.add(InsightNarrativeCache(
        user_id=1, days=7, language="en", repo_id=None, response_json={},
        created_at=_T0, expires_at=_T0, last_error_at=_T0, error_count=1, last_error_type=None,
    ))
    db.commit()
    assert _dash(db, now=_T0 + timedelta(seconds=1)) is None


def test_ttl_boundary_is_strict(db):
    """경계 — 119.999 s 는 적중, 정확히 120 s 는 비적중."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error", now=_T0)
    assert _dash(db, now=_T0 + timedelta(seconds=119, microseconds=999_000)) == "api_error"
    assert _dash(db, now=_T0 + timedelta(seconds=120)) is None
    assert _dash(db, now=_T0 + timedelta(seconds=121)) is None


def test_within_seconds_overrides_the_window(db):
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error", now=_T0)
    assert _dash(db, now=_T0 + timedelta(seconds=30), within_seconds=10) is None
    assert _dash(db, now=_T0 + timedelta(seconds=30), within_seconds=60) == "api_error"


def test_naive_and_aware_now_are_both_accepted(db):
    """이 리포는 aware(서비스)·naive(컬럼) 가 섞인다 — 어느 쪽 `now` 든 같은 판정."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error", now=_T0)
    aware = _T0 + timedelta(seconds=30)
    naive = aware.replace(tzinfo=None)
    assert _dash(db, now=aware) == "api_error"
    assert _dash(db, now=naive) == "api_error"
    # 창 밖도 양쪽이 같다 / outside the window both agree too
    assert _dash(db, now=(_T0 + timedelta(seconds=200)).replace(tzinfo=None)) is None


def test_non_utc_aware_now_is_compared_in_utc(db):
    """aware `now` 가 UTC 가 아니어도 같은 순간이면 같은 판정이다."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error", now=_T0)
    seoul = timezone(timedelta(hours=9))
    assert _dash(db, now=(_T0 + timedelta(seconds=30)).astimezone(seoul)) == "api_error"
    assert _dash(db, now=(_T0 + timedelta(seconds=300)).astimezone(seoul)) is None


def test_default_now_uses_the_clock(db):
    """`now` 생략 — 방금 기록한 실패는 적중, 오래전 실패는 비적중."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error")
    assert repo_mod.recent_error(db, user_id=1, days=7, language="en") == "api_error"
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=30, language="en",
                               error_type="api_error", now=datetime.now(timezone.utc) - timedelta(hours=1))
    assert repo_mod.recent_error_repo(db, user_id=1, repo_id=5, days=30, language="en") is None


def test_error_stamped_far_in_the_future_does_not_block(db):
    """시계·세션 TZ 가 어긋나 미래로 찍힌 실패는 창보다 오래 막지 않는다 — 조금 앞선 것(경합)은 적중."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error",
                          now=_T0 + timedelta(hours=9))
    assert _dash(db, now=_T0) is None
    repo_mod.record_error(db, user_id=2, days=7, language="en", error_type="api_error",
                          now=_T0 + timedelta(seconds=2))
    assert _dash(db, now=_T0, user_id=2) == "api_error"


# ─── 키 격리 ──────────────────────────────────────────────────────────────────


def test_dashboard_key_ignores_repo_rows(db):
    """대시보드 키는 `repo_id IS NULL` 이다 — 같은 사용자·기간·언어의 리포 실패가 새지 않는다."""
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=7, language="en",
                               error_type="APITimeoutError", now=_T0)
    assert _dash(db, now=_T0 + timedelta(seconds=5), days=7) is None


def test_repo_key_ignores_dashboard_rows_and_other_repos(db):
    repo_mod.record_error(db, user_id=1, days=30, language="en", error_type="api_error", now=_T0)
    repo_mod.record_error_repo(db, user_id=1, repo_id=6, days=30, language="en",
                               error_type="APITimeoutError", now=_T0)
    assert _repo(db, now=_T0 + timedelta(seconds=5), repo_id=5) is None
    assert _repo(db, now=_T0 + timedelta(seconds=5), repo_id=6) == "APITimeoutError"


@pytest.mark.parametrize("field, other", [("user_id", 2), ("days", 30), ("language", "ko")])
def test_dashboard_key_is_isolated_per_user_days_language(db, field, other):
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error", now=_T0)
    kwargs = {"user_id": 1, "days": 7, "language": "en", field: other}
    assert repo_mod.recent_error(db, now=_T0 + timedelta(seconds=5), **kwargs) is None


@pytest.mark.parametrize("field, other", [("user_id", 2), ("days", 7), ("language", "ko")])
def test_repo_key_is_isolated_per_user_days_language(db, field, other):
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=30, language="en",
                               error_type="APITimeoutError", now=_T0)
    kwargs = {"user_id": 1, "repo_id": 5, "days": 30, "language": "en", field: other}
    assert repo_mod.recent_error_repo(db, now=_T0 + timedelta(seconds=5), **kwargs) is None


# ─── 성공이 실패를 지운다 ────────────────────────────────────────────────────


def test_success_upsert_clears_the_dashboard_error_but_keeps_the_count(db):
    """실패 뒤 성공(새로 고침 등)하면 더 오래된 실패가 다음 조회를 막지 않는다."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error", now=_T0)
    repo_mod.upsert(db, user_id=1, days=7, language="en", response={"status": "success"},
                    ttl_seconds=1, now=_T0 + timedelta(seconds=5))
    # 성공 캐시가 만료된 뒤에도(ttl 1 s) 실패가 되살아나지 않는다
    # Even after the success cache expires the old failure does not come back.
    assert _dash(db, now=_T0 + timedelta(seconds=10)) is None
    row = db.query(InsightNarrativeCache).one()
    assert row.last_error_at is None and row.last_error_type is None
    assert row.error_count == 1


def test_success_upsert_repo_clears_the_repo_error_but_keeps_the_count(db):
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=30, language="en",
                               error_type="APITimeoutError", now=_T0)
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=30, language="en",
                               error_type="APITimeoutError", now=_T0 + timedelta(seconds=1))
    repo_mod.upsert_repo(db, user_id=1, repo_id=5, days=30, language="en",
                         response={"text": "t", "status": "success"}, ttl_seconds=1,
                         now=_T0 + timedelta(seconds=5))
    assert _repo(db, now=_T0 + timedelta(seconds=10)) is None
    row = db.query(InsightNarrativeCache).one()
    assert row.last_error_at is None and row.last_error_type is None
    assert row.error_count == 2


# ─── 보존 스윕 ────────────────────────────────────────────────────────────────


def test_purge_spares_a_recent_error_row_and_deletes_an_old_one(db):
    """실패 행은 태어날 때 만료라 스윕이 곧바로 지우면 부정 상태가 창보다 먼저 사라진다."""
    repo_mod.record_error(db, user_id=1, days=7, language="en", error_type="api_error", now=_T0)
    repo_mod.record_error_repo(db, user_id=1, repo_id=5, days=30, language="en",
                               error_type="TimeoutError", now=_T0)
    repo_mod.record_error(db, user_id=2, days=7, language="en", error_type="api_error",
                          now=_T0 - timedelta(seconds=300))

    deleted = repo_mod.purge_expired(db, now=_T0 + timedelta(seconds=30))

    assert deleted == 1
    assert {(r.user_id, r.repo_id) for r in db.query(InsightNarrativeCache).all()} == {(1, None), (1, 5)}
    assert _dash(db, now=_T0 + timedelta(seconds=30)) == "api_error"
    assert _repo(db, now=_T0 + timedelta(seconds=30)) == "TimeoutError"

    # 창이 지나면 같은 행도 지운다 / once the window passes the same rows go too
    assert repo_mod.purge_expired(db, now=_T0 + timedelta(seconds=121)) == 2
    assert db.query(InsightNarrativeCache).count() == 0


def test_purge_still_deletes_expired_success_rows(db):
    """`last_error_at` 이 NULL 인 만료 행은 예전처럼 지운다."""
    repo_mod.upsert(db, user_id=1, days=7, language="en", response={"s": 1}, ttl_seconds=60, now=_T0)
    assert repo_mod.purge_expired(db, now=_T0 + timedelta(seconds=61)) == 1
