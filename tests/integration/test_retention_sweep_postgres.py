"""retention sweep GC (purge_expired / purge_terminal) PostgreSQL round-trip 검증 (회고 P2#43).

#1075 데이터 보존 sweep 의 파괴적 DELETE 정확성이 non-production 엔진(SQLite)에서만 검증됐다.
naive DateTime 컬럼(`expires_at`·`updated_at`)과 aware `now` 정규화(`now.replace(tzinfo=None)`)의
정합이 PostgreSQL(TIMESTAMP WITHOUT TIME ZONE)에서도 **정확히 예상 집합만** 삭제하는지 확인하고,
비-UTC 세션 TimeZone 에서도 UTC 가정이 무너지지 않음을 lock 한다.

The #1075 retention DELETE was only proven on SQLite. This verifies the naive/aware coercion deletes
exactly the expected set on PostgreSQL, including under a non-UTC session TimeZone.

실행 조건 / Execution guard: DATABASE_URL_TEST_POSTGRES 설정 시에만 (pg-concurrency CI job).
로컬 SQLite 는 자동 skip — 명시 단일 파일이라 e2e/integration 혼입 없음(testing.md pg-concurrency 규칙).
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

_PG_URL = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
_requires_postgres = pytest.mark.skipif(
    not _PG_URL, reason="retention sweep PG test requires DATABASE_URL_TEST_POSTGRES",
)


def test_ci_wires_retention_sweep_into_pg_concurrency_job():
    """🔴 이 파일이 pg-concurrency CI job 에 배선됐는지 (PG-gated 라 로컬 skip → CI 만 실행 =
    배선 누락 시 영영 미실행). 이 메타-가드는 비-PG 라 로컬에서도 돌아 배선을 잠근다."""
    from pathlib import Path  # pylint: disable=import-outside-toplevel

    import yaml  # pylint: disable=import-outside-toplevel

    ci = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml")
        .read_text(encoding="utf-8")
    )
    runs = " ".join(
        s.get("run", "") for s in ci["jobs"]["pg-concurrency"]["steps"] if "run" in s
    )
    assert "test_retention_sweep_postgres.py" in runs, (
        "retention sweep PG 테스트가 pg-concurrency job 에 미배선 — PG-gated 라 CI 에서도 미실행"
    )

# aware(UTC) 고정 now — retention 함수가 naive 로 정규화하는지 검증하는 기준 시각.
# Fixed aware(UTC) now — the reference the retention functions must normalize to naive.
_NOW = datetime(2030, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
_NAIVE_NOW = _NOW.replace(tzinfo=None)


def _fresh_session():
    """PG 세션 — 이전 테스트 잔류 제거(drop_all/create_all) 후 clean slate (기존 PG 테스트 패턴)."""
    from src.database import Base  # pylint: disable=import-outside-toplevel

    engine = create_engine(_PG_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_user(session):
    from src.models.user import User  # pylint: disable=import-outside-toplevel

    user = User(
        github_id="ret-p2-43", github_login="rettest", github_access_token="x",
        email="ret@example.com", display_name="Ret Test",  # display_name NOT NULL (PG 강제)
    )
    session.add(user)
    session.flush()
    return user.id


def _seed_repo_analysis(session, pr):
    """Repository + Analysis (analysis_id NOT NULL FK 충족) → analysis_id 반환."""
    from src.models.analysis import Analysis  # pylint: disable=import-outside-toplevel
    from src.models.repository import Repository  # pylint: disable=import-outside-toplevel

    repo = session.query(Repository).filter_by(full_name="ret/repo").first()
    if repo is None:
        repo = Repository(full_name="ret/repo")
        session.add(repo)
        session.flush()
    analysis = Analysis(
        repo_id=repo.id, commit_sha=f"sha{pr}", score=80, grade="B",
        result={}, pr_number=pr,
    )
    session.add(analysis)
    session.flush()
    return analysis.id


def _seed_cache(session, user_id, *, days, expires_at):
    # 🔴 days 를 행마다 달리 준다 — insight_narrative_cache 는 UNIQUE(user_id, days, language)
    # 라 같은 (user_id, days, language) 두 행은 IntegrityError (PG·SQLite 공통).
    from src.models.insight_narrative_cache import (  # pylint: disable=import-outside-toplevel
        InsightNarrativeCache,
    )

    row = InsightNarrativeCache(
        user_id=user_id, repo_id=None, days=days, language="en",
        response_json={}, expires_at=expires_at,
    )
    session.add(row)
    session.commit()
    return row.id


def _seed_merge_row(session, *, pr, status, updated_at):
    from src.models.merge_retry import MergeRetryQueue  # pylint: disable=import-outside-toplevel

    analysis_id = _seed_repo_analysis(session, pr)
    row = MergeRetryQueue(
        repo_full_name="ret/repo", pr_number=pr, analysis_id=analysis_id,
        commit_sha=f"sha{pr}", score=80, threshold_at_enqueue=75,
        status=status, attempts_count=0, max_attempts=30,
        next_retry_at=datetime(2020, 1, 1), updated_at=updated_at,  # 명시 → default override
    )
    session.add(row)
    session.commit()
    return row.id


@_requires_postgres
def test_purge_expired_deletes_only_past_rows_on_postgres():
    """purge_expired: `expires_at < now` 만 삭제, fresh 보존 (naive/aware 정합, PG)."""
    from src.models.insight_narrative_cache import (  # pylint: disable=import-outside-toplevel
        InsightNarrativeCache,
    )
    from src.repositories import insight_narrative_cache_repo  # pylint: disable=import-outside-toplevel

    session = _fresh_session()
    try:
        uid = _seed_user(session)
        expired = _seed_cache(session, uid, days=7, expires_at=_NAIVE_NOW - timedelta(hours=1))
        fresh = _seed_cache(session, uid, days=30, expires_at=_NAIVE_NOW + timedelta(hours=1))

        deleted = insight_narrative_cache_repo.purge_expired(session, now=_NOW)  # aware now

        assert deleted == 1, "만료 1건만 삭제돼야 함 (naive/aware coercion PG 정합)"
        remaining = {r.id for r in session.query(InsightNarrativeCache).all()}
        assert expired not in remaining, "만료 행 미삭제"
        assert fresh in remaining, "fresh 행 오삭제 (경계 오류)"
    finally:
        session.close()


@_requires_postgres
def test_purge_terminal_deletes_old_terminal_preserves_pending_on_postgres():
    """purge_terminal: 오래된 종결행만 삭제 · pending 절대보존 · recent 종결 보존 (PG)."""
    from src.models.merge_retry import MergeRetryQueue  # pylint: disable=import-outside-toplevel
    from src.repositories import merge_retry_repo  # pylint: disable=import-outside-toplevel

    session = _fresh_session()
    try:
        old_terminal = _seed_merge_row(
            session, pr=1, status="succeeded", updated_at=_NAIVE_NOW - timedelta(days=10),
        )  # 종결 + >7d → 삭제
        recent_terminal = _seed_merge_row(
            session, pr=2, status="abandoned", updated_at=_NAIVE_NOW - timedelta(days=2),
        )  # 종결 + <7d → 보존
        old_pending = _seed_merge_row(
            session, pr=3, status="pending", updated_at=_NAIVE_NOW - timedelta(days=10),
        )  # pending → 절대보존(오래됐어도)

        deleted = merge_retry_repo.purge_terminal(session, older_than_days=7, now=_NOW)

        assert deleted == 1, "오래된 종결 1건만 삭제돼야 함"
        remaining = {r.id for r in session.query(MergeRetryQueue).all()}
        assert old_terminal not in remaining, "오래된 종결 미삭제"
        assert recent_terminal in remaining, "recent 종결 오삭제 (cutoff 경계 오류)"
        assert old_pending in remaining, "🔴 pending 오삭제 — 절대보존 위반"
    finally:
        session.close()


@_requires_postgres
def test_purge_correct_under_non_utc_session_timezone():
    """🔴 비-UTC 세션 TimeZone 에서도 동일 집합 삭제 — naive TIMESTAMP 라 세션 TZ 무관(UTC 가정 lock)."""
    from src.models.insight_narrative_cache import (  # pylint: disable=import-outside-toplevel
        InsightNarrativeCache,
    )
    from src.repositories import insight_narrative_cache_repo  # pylint: disable=import-outside-toplevel

    session = _fresh_session()
    try:
        session.execute(text("SET TimeZone = 'America/New_York'"))
        uid = _seed_user(session)
        expired = _seed_cache(session, uid, days=7, expires_at=_NAIVE_NOW - timedelta(hours=1))
        fresh = _seed_cache(session, uid, days=30, expires_at=_NAIVE_NOW + timedelta(hours=1))

        deleted = insight_narrative_cache_repo.purge_expired(session, now=_NOW)

        assert deleted == 1, "세션 TZ(America/New_York)가 naive 비교를 흔들면 안 됨"
        remaining = {r.id for r in session.query(InsightNarrativeCache).all()}
        assert expired not in remaining and fresh in remaining
    finally:
        session.close()
