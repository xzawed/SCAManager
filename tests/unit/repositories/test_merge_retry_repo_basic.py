"""Basic CRUD tests for merge_retry_repo (T1 — claim semantics in T6).

merge_retry_repo 기본 CRUD 단위 테스트 (T1 — claim 의미론은 T6 에서 추가).

테스트 목록:
- test_get_returns_none_for_missing_id
- test_list_pending_filters_by_status_and_next_retry_at
- test_list_pending_excludes_non_pending_status
- test_get_by_sha_returns_none_when_no_match
- test_delete_all_for_repo_returns_count
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
from src.models.merge_retry import MergeRetryQueue
from src.models.repository import Repository
from src.repositories import merge_retry_repo


@pytest.fixture
def db_session():
    """인메모리 SQLite DB 세션 — 각 테스트 후 폐기.
    In-memory SQLite session — discarded after each test.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_analysis(db_session, commit_sha: str = "abc123") -> Analysis:
    """테스트용 Repository + Analysis 시드 데이터 삽입.
    Insert seed Repository + Analysis for tests.
    """
    # 동일 리포 재사용 — full_name 중복 방지
    # Reuse same repo — prevent full_name duplicate.
    repo = db_session.query(Repository).filter_by(full_name="owner/repo").first()
    if repo is None:
        repo = Repository(full_name="owner/repo")
        db_session.add(repo)
        db_session.commit()
    analysis = Analysis(
        repo_id=repo.id,
        commit_sha=commit_sha,
        score=80,
        grade="B",
        result={},
    )
    db_session.add(analysis)
    db_session.commit()
    return analysis


def _make_queue_row(  # pylint: disable=too-many-arguments
    db_session,
    *,
    analysis_id: int,
    repo_full_name: str = "owner/repo",
    pr_number: int = 1,
    commit_sha: str = "abc123",
    score: int = 80,
    threshold_at_enqueue: int = 75,
    status: str = "pending",
    next_retry_at: datetime | None = None,
) -> MergeRetryQueue:
    """MergeRetryQueue 행을 직접 삽입하는 헬퍼.
    Helper that inserts a MergeRetryQueue row directly.
    """
    now = datetime.now(timezone.utc)
    row = MergeRetryQueue(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        analysis_id=analysis_id,
        commit_sha=commit_sha,
        score=score,
        threshold_at_enqueue=threshold_at_enqueue,
        status=status,
        next_retry_at=next_retry_at if next_retry_at is not None else now,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1. get()
# ---------------------------------------------------------------------------

def test_get_returns_none_for_missing_id(db_session):
    """존재하지 않는 ID 조회 시 None 반환.
    get() returns None for an ID that does not exist.
    """
    result = merge_retry_repo.get(db_session, 9999)
    assert result is None


def test_get_returns_row_when_exists(db_session):
    """존재하는 ID 조회 시 MergeRetryQueue 반환.
    get() returns the MergeRetryQueue row when it exists.
    """
    analysis = _seed_analysis(db_session)
    row = _make_queue_row(db_session, analysis_id=analysis.id)

    result = merge_retry_repo.get(db_session, row.id)
    assert result is not None
    assert result.id == row.id
    assert result.repo_full_name == "owner/repo"


# ---------------------------------------------------------------------------
# 2. list_pending()
# ---------------------------------------------------------------------------

def test_list_pending_filters_by_status_and_next_retry_at(db_session):
    """status='pending' AND next_retry_at <= now 인 행만 반환.
    list_pending() returns only rows with status='pending' AND next_retry_at <= now.
    """
    analysis = _seed_analysis(db_session)
    now = datetime.now(timezone.utc)

    # 조건 충족 — next_retry_at 이 과거
    # Matches — next_retry_at is in the past.
    past_row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        pr_number=1,
        commit_sha="sha001",
        next_retry_at=now - timedelta(minutes=5),
    )

    # 조건 미충족 — next_retry_at 이 미래
    # Does not match — next_retry_at is in the future.
    _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        pr_number=2,
        commit_sha="sha002",
        next_retry_at=now + timedelta(minutes=10),
    )

    rows = merge_retry_repo.list_pending(db_session, now=now)
    assert len(rows) == 1
    assert rows[0].id == past_row.id


def test_list_pending_excludes_non_pending_status(db_session):
    """status != 'pending' 인 행은 list_pending 에서 제외된다.
    list_pending() excludes rows whose status is not 'pending'.
    """
    analysis = _seed_analysis(db_session)
    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=1)

    # succeeded 상태 — 제외되어야 함
    # succeeded status — must be excluded.
    _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        pr_number=10,
        commit_sha="sha_succ",
        status="succeeded",
        next_retry_at=past,
    )

    # pending 상태 — 포함되어야 함
    # pending status — must be included.
    pending_row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        pr_number=11,
        commit_sha="sha_pend",
        status="pending",
        next_retry_at=past,
    )

    rows = merge_retry_repo.list_pending(db_session, now=now)
    assert len(rows) == 1
    assert rows[0].id == pending_row.id


def test_list_pending_ordered_by_next_retry_at_asc(db_session):
    """list_pending 은 next_retry_at ASC 정렬로 반환한다.
    list_pending() returns rows ordered by next_retry_at ASC.
    """
    analysis = _seed_analysis(db_session)
    now = datetime.now(timezone.utc)

    later = _make_queue_row(
        db_session, analysis_id=analysis.id, pr_number=20,
        commit_sha="sha_later", next_retry_at=now - timedelta(minutes=1),
    )
    earlier = _make_queue_row(
        db_session, analysis_id=analysis.id, pr_number=21,
        commit_sha="sha_earlier", next_retry_at=now - timedelta(minutes=10),
    )

    rows = merge_retry_repo.list_pending(db_session, now=now)
    assert len(rows) == 2
    # 더 이른 next_retry_at 이 먼저 나와야 한다
    # The earlier next_retry_at must come first.
    assert rows[0].id == earlier.id
    assert rows[1].id == later.id


# ---------------------------------------------------------------------------
# 3. get_by_sha()
# ---------------------------------------------------------------------------

def test_get_by_sha_returns_none_when_no_match(db_session):
    """일치하는 (repo_full_name, commit_sha) 이 없으면 None 반환.
    get_by_sha() returns None when no row matches (repo_full_name, commit_sha).
    """
    result = merge_retry_repo.get_by_sha(
        db_session,
        repo_full_name="owner/repo",
        commit_sha="nonexistent_sha",
    )
    assert result is None


def test_get_by_sha_returns_pending_row(db_session):
    """pending 상태 행이 있으면 반환한다.
    get_by_sha() returns the pending row when it exists.
    """
    analysis = _seed_analysis(db_session)
    row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="findme_sha",
        status="pending",
    )

    result = merge_retry_repo.get_by_sha(
        db_session,
        repo_full_name="owner/repo",
        commit_sha="findme_sha",
    )
    assert result is not None
    assert result.id == row.id


def test_get_by_sha_excludes_succeeded_rows(db_session):
    """succeeded 상태 행은 get_by_sha 에서 제외된다.
    get_by_sha() excludes rows with terminal status (succeeded).
    """
    analysis = _seed_analysis(db_session)
    _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="done_sha",
        status="succeeded",
    )

    result = merge_retry_repo.get_by_sha(
        db_session,
        repo_full_name="owner/repo",
        commit_sha="done_sha",
    )
    assert result is None


# ---------------------------------------------------------------------------
# 4. delete_all_for_repo()
# ---------------------------------------------------------------------------

def test_delete_all_for_repo_returns_count(db_session):
    """delete_all_for_repo 는 삭제된 행 수를 반환한다.
    delete_all_for_repo() returns the count of deleted rows.
    """
    analysis = _seed_analysis(db_session)

    # 3개 행 삽입
    # Insert 3 rows.
    for i in range(3):
        _make_queue_row(
            db_session,
            analysis_id=analysis.id,
            pr_number=i + 1,
            commit_sha=f"sha_{i}",
        )

    count = merge_retry_repo.delete_all_for_repo(
        db_session, repo_full_name="owner/repo"
    )
    assert count == 3
    assert db_session.query(MergeRetryQueue).count() == 0


def test_delete_all_for_repo_only_deletes_matching_repo(db_session):
    """다른 리포의 행은 삭제하지 않는다.
    delete_all_for_repo() does not delete rows belonging to other repos.
    """
    analysis = _seed_analysis(db_session)

    # 다른 리포 생성
    # Create a different repo.
    other_repo = Repository(full_name="other/repo")
    db_session.add(other_repo)
    db_session.commit()
    other_analysis = Analysis(
        repo_id=other_repo.id, commit_sha="other_sha", score=70, grade="C", result={}
    )
    db_session.add(other_analysis)
    db_session.commit()

    # owner/repo 에 2개, other/repo 에 1개 삽입
    # 2 rows for owner/repo, 1 row for other/repo.
    _make_queue_row(
        db_session, analysis_id=analysis.id, pr_number=1, commit_sha="sha_a"
    )
    _make_queue_row(
        db_session, analysis_id=analysis.id, pr_number=2, commit_sha="sha_b"
    )
    _make_queue_row(
        db_session,
        analysis_id=other_analysis.id,
        pr_number=3,
        commit_sha="sha_c",
        repo_full_name="other/repo",
    )

    count = merge_retry_repo.delete_all_for_repo(
        db_session, repo_full_name="owner/repo"
    )
    assert count == 2
    # other/repo 의 행은 남아 있어야 한다
    # Row for other/repo must remain.
    assert db_session.query(MergeRetryQueue).count() == 1
