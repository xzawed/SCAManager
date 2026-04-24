"""merge_attempt_repo — MergeAttempt 쿼리/집계 단위 테스트 (Phase F.1).

TDD Red: src/repositories/merge_attempt_repo.py 모듈은 아직 없음.

- create(): 항상 INSERT (upsert 아님 — 모든 시도 이력 보존).
- list_by_repo(): attempted_at DESC 정렬 + limit.
- count_failures_by_reason(): success=False 만 실패 사유별 집계 + since 파라미터.
"""
# pylint: disable=redefined-outer-name
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_attempt import MergeAttempt
from src.models.repository import Repository
from src.repositories import merge_attempt_repo


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_analysis(db_session, commit_sha="abc123") -> Analysis:
    # 동일 repo 를 재사용 — full_name 중복 시 insert 실패하므로 조회 우선
    repo = db_session.query(Repository).filter_by(full_name="owner/repo").first()
    if repo is None:
        repo = Repository(full_name="owner/repo")
        db_session.add(repo)
        db_session.commit()
    a = Analysis(repo_id=repo.id, commit_sha=commit_sha, score=80, grade="B", result={})
    db_session.add(a)
    db_session.commit()
    return a


def test_create_inserts_new_record(db_session):
    """기본 INSERT — 반환된 레코드의 필드가 모두 저장 파라미터와 일치한다."""
    a = _seed_analysis(db_session)
    rec = merge_attempt_repo.create(
        db_session,
        analysis_id=a.id,
        repo_name="owner/repo",
        pr_number=1,
        score=80,
        threshold=75,
        success=True,
    )
    assert rec.id is not None
    assert rec.analysis_id == a.id
    assert rec.success is True
    assert rec.failure_reason is None
    assert db_session.query(MergeAttempt).count() == 1


def test_create_allows_duplicate_analysis_id(db_session):
    """동일 analysis_id 로 여러 시도 기록 허용 — 재시도 이력 보존 (upsert 아님)."""
    a = _seed_analysis(db_session)
    merge_attempt_repo.create(
        db_session,
        analysis_id=a.id,
        repo_name="owner/repo",
        pr_number=1,
        score=80,
        threshold=75,
        success=False,
        failure_reason="dirty_conflict",
        detail_message="dirty_conflict: merge conflict",
    )
    merge_attempt_repo.create(
        db_session,
        analysis_id=a.id,  # 동일 analysis_id — 두 번째 시도
        repo_name="owner/repo",
        pr_number=1,
        score=80,
        threshold=75,
        success=True,
    )
    assert db_session.query(MergeAttempt).count() == 2


def test_list_by_repo_returns_latest_first(db_session):
    """attempted_at DESC 정렬 + limit 적용 — 최신 시도가 첫 번째."""
    a = _seed_analysis(db_session)
    base = datetime(2026, 4, 24, 10, 0, 0, tzinfo=timezone.utc)
    # 오래된 시도
    old = MergeAttempt(
        analysis_id=a.id, repo_name="owner/repo", pr_number=1,
        score=70, threshold=75, success=False, failure_reason="unknown",
        attempted_at=base - timedelta(hours=2),
    )
    mid = MergeAttempt(
        analysis_id=a.id, repo_name="owner/repo", pr_number=1,
        score=75, threshold=75, success=False, failure_reason="unstable_ci",
        attempted_at=base - timedelta(hours=1),
    )
    new = MergeAttempt(
        analysis_id=a.id, repo_name="owner/repo", pr_number=1,
        score=80, threshold=75, success=True,
        attempted_at=base,
    )
    db_session.add_all([old, mid, new])
    db_session.commit()

    # 다른 리포의 시도는 포함되지 않아야 함
    other_repo = Repository(full_name="other/repo")
    db_session.add(other_repo)
    db_session.commit()
    other_a = Analysis(repo_id=other_repo.id, commit_sha="xyz", score=80, grade="B", result={})
    db_session.add(other_a)
    db_session.commit()
    db_session.add(MergeAttempt(
        analysis_id=other_a.id, repo_name="other/repo", pr_number=1,
        score=80, threshold=75, success=True, attempted_at=base,
    ))
    db_session.commit()

    rows = merge_attempt_repo.list_by_repo(db_session, "owner/repo", limit=50)
    assert len(rows) == 3
    assert rows[0].score == 80  # 가장 최근
    assert rows[1].score == 75
    assert rows[2].score == 70

    # limit 적용 — 최신 2건만
    rows_limited = merge_attempt_repo.list_by_repo(db_session, "owner/repo", limit=2)
    assert len(rows_limited) == 2
    assert rows_limited[0].score == 80
    assert rows_limited[1].score == 75


def test_count_failures_by_reason_aggregates(db_session):
    """실패 건만 사유별 집계 — success=True 는 제외, since 파라미터로 기간 필터."""
    a = _seed_analysis(db_session)
    base = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)
    cutoff = base - timedelta(days=1)

    attempts = [
        # 최근 실패들
        MergeAttempt(
            analysis_id=a.id, repo_name="owner/repo", pr_number=1,
            score=70, threshold=75, success=False,
            failure_reason="branch_protection_blocked",
            attempted_at=base,
        ),
        MergeAttempt(
            analysis_id=a.id, repo_name="owner/repo", pr_number=2,
            score=71, threshold=75, success=False,
            failure_reason="branch_protection_blocked",
            attempted_at=base - timedelta(hours=1),
        ),
        MergeAttempt(
            analysis_id=a.id, repo_name="owner/repo", pr_number=3,
            score=72, threshold=75, success=False,
            failure_reason="dirty_conflict",
            attempted_at=base - timedelta(hours=2),
        ),
        # 성공 — 집계 제외
        MergeAttempt(
            analysis_id=a.id, repo_name="owner/repo", pr_number=4,
            score=90, threshold=75, success=True,
            attempted_at=base,
        ),
        # 예전 실패 — since 파라미터로 제외되어야 함
        MergeAttempt(
            analysis_id=a.id, repo_name="owner/repo", pr_number=5,
            score=60, threshold=75, success=False,
            failure_reason="unknown",
            attempted_at=base - timedelta(days=7),
        ),
    ]
    db_session.add_all(attempts)
    db_session.commit()

    # since=None → 전체 집계 (성공 제외)
    all_counts = merge_attempt_repo.count_failures_by_reason(db_session, since=None)
    assert all_counts.get("branch_protection_blocked") == 2
    assert all_counts.get("dirty_conflict") == 1
    assert all_counts.get("unknown") == 1
    # 성공은 키로 나타나지 않음
    assert "success" not in all_counts
    assert None not in all_counts

    # since=cutoff → 지난 24h 내 실패만
    recent_counts = merge_attempt_repo.count_failures_by_reason(
        db_session, since=cutoff,
    )
    assert recent_counts.get("branch_protection_blocked") == 2
    assert recent_counts.get("dirty_conflict") == 1
    # 7일 전 실패는 제외
    assert "unknown" not in recent_counts


def test_count_failures_by_reason_empty_when_no_failures(db_session):
    """실패 레코드가 전혀 없으면 빈 dict 반환."""
    a = _seed_analysis(db_session)
    merge_attempt_repo.create(
        db_session,
        analysis_id=a.id, repo_name="owner/repo", pr_number=1,
        score=90, threshold=75, success=True,
    )
    counts = merge_attempt_repo.count_failures_by_reason(db_session)
    assert counts == {}
