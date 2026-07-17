"""analysis_attempt_repo 단위 테스트 — 분석 소실 탐지용 attempt 행 수명주기.

Unit tests for analysis_attempt_repo — lifecycle of the attempt row used to detect lost analyses.

배경 / Background
----------------
분석 파이프라인은 in-process BackgroundTask 로 실행되고 GitHub 에는 즉시 200 을 선반환한다
(`src/webhook/providers/github.py`). 유일한 내구 기록인 `Analysis` 행은 GitHub API 파일 수집 +
Claude 리뷰(60s+) 가 **끝난 뒤** 저장되므로, 그 사이 SIGTERM/OOM/크래시가 나면 분석이 조용히
증발하고 "아직 분석 안 됨" 과 영영 구별할 수 없다.

The pipeline runs as an in-process BackgroundTask and returns 200 to GitHub immediately. The only
durable record (`Analysis`) is written *after* file collection + the Claude review, so a crash in
that window makes the analysis vanish indistinguishably from "not analyzed yet".

`analysis_attempts` 는 비싼 작업 **전에** 행을 남기고 정상 종료 시 지우는 tombstone 이다 —
남아있는 행 = 소실된 분석 (`find_orphaned` 로 탐지).
`analysis_attempts` is a tombstone written *before* the expensive work and deleted on normal
completion — a surviving row means a lost analysis (surfaced by `find_orphaned`).
"""
# pylint: disable=redefined-outer-name
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base

# 🔴 src/models/__init__.py 는 빈 파일 — Base.metadata.create_all() 전에 각 ORM 모델을 명시적으로
# import 해야 테이블이 in-memory SQLite 에 생성된다 (testing.md 사이클 115 규칙).
# 🔴 src/models/__init__.py is empty — each ORM model must be imported explicitly before
# Base.metadata.create_all(), otherwise the table is never created (testing.md cycle 115 rule).
from src.models.analysis_attempt import AnalysisAttempt  # noqa: F401
from src.models.repository import Repository  # noqa: F401
from src.repositories import analysis_attempt_repo


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


def _seed_repo(db, full_name: str = "owner/repo") -> Repository:
    """FK 대상 Repository 1건 생성.
    Create the Repository row that attempts reference via FK."""
    repo = Repository(full_name=full_name)
    db.add(repo)
    db.commit()
    return repo


def _now_naive() -> datetime:
    """naive UTC now — `started_at` 은 timezone-naive DateTime 컬럼 (merge_retry_repo 컨벤션).
    Naive UTC now — `started_at` is a timezone-naive DateTime column (merge_retry_repo convention)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── begin_attempt ────────────────────────────────────────────────────────────


def test_begin_attempt_inserts_row_and_returns_true(db_session):
    """계약 1 — 정상 INSERT 시 True 반환 + 행이 실제로 영속화되고 필드가 round-trip 한다."""
    # Contract 1 — a fresh insert returns True and the row round-trips with all fields.
    repo = _seed_repo(db_session)

    won = analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=7, event="pull_request",
    )

    assert won is True
    rows = db_session.query(AnalysisAttempt).all()
    assert len(rows) == 1
    assert rows[0].repo_id == repo.id
    assert rows[0].commit_sha == "abc123"
    assert rows[0].pr_number == 7
    assert rows[0].event == "pull_request"
    # started_at 은 nullable=False + default — 호출자가 안 넘겨도 채워져야 한다
    # started_at is nullable=False with a default — populated without the caller passing it
    assert rows[0].started_at is not None


def test_begin_attempt_allows_null_pr_number_for_push(db_session):
    """push 이벤트는 pr_number 없이 시작할 수 있어야 한다 (nullable=True)."""
    # Push events must be able to begin without a pr_number (nullable=True).
    repo = _seed_repo(db_session)

    won = analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="def456", pr_number=None, event="push",
    )

    assert won is True
    row = db_session.query(AnalysisAttempt).one()
    assert row.pr_number is None
    assert row.event == "push"


def test_begin_attempt_duplicate_returns_false_without_raising(db_session):
    """계약 2 — 동일 (repo_id, commit_sha) 2차 호출은 UNIQUE 위반을 흡수해 False 반환.

    Contract 2 — a second begin for the same (repo_id, commit_sha) absorbs the UNIQUE
    violation and returns False. 동시 웹훅이 먼저 시작한 정상 상황이므로 IntegrityError 를
    호출자에게 전파하면 안 된다 (파이프라인 abort → 오히려 분석 소실).
    A concurrent webhook winning the race is *normal* — propagating IntegrityError would abort
    the pipeline and cause the very loss this table exists to detect.
    """
    repo = _seed_repo(db_session)
    assert analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=7, event="pull_request",
    ) is True

    # 2차 호출 — 예외가 새어나오면 이 라인에서 테스트가 죽는다 (= 계약 위반)
    # Second call — if the exception leaks, the test dies right here (= contract violation)
    lost = analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=9, event="push",
    )

    assert lost is False
    # 중복 INSERT 없음 + 최초 행 보존 (덮어쓰기 금지)
    # No duplicate insert; the first row is preserved (no overwrite)
    rows = db_session.query(AnalysisAttempt).all()
    assert len(rows) == 1
    assert rows[0].pr_number == 7
    assert rows[0].event == "pull_request"


def test_begin_attempt_duplicate_leaves_session_usable(db_session):
    """계약 2 — 실패 후 세션이 rollback 되어 계속 사용 가능해야 한다.

    Contract 2 — the session must be rolled back and remain usable after the failure.
    rollback 누락 시 세션이 'PendingRollbackError' 상태로 오염되어 이후 파이프라인 단계
    (Analysis 저장 등) 가 전부 실패한다 — 조용한 소실의 새 원인이 된다.
    Without the rollback the session is poisoned (PendingRollbackError) and every later
    pipeline step fails — creating a *new* silent-loss path.
    """
    repo = _seed_repo(db_session)
    analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=None, event="push",
    )
    analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=None, event="push",
    )

    # 세션이 살아있음을 실제 쓰기로 증명 — 오염된 세션이면 여기서 PendingRollbackError
    # Prove the session is alive with a real write — a poisoned session raises here
    db_session.add(Repository(full_name="owner/other"))
    db_session.commit()
    assert db_session.query(Repository).count() == 2


def test_begin_attempt_allows_same_sha_across_different_repos(db_session):
    """UNIQUE 는 (repo_id, commit_sha) 복합 — 다른 리포의 동일 SHA 는 차단되면 안 된다.

    The UNIQUE constraint is composite (repo_id, commit_sha) — the same SHA in a *different*
    repo must not be blocked (fork/cherry-pick 시 동일 SHA 공유 가능).
    """
    repo_a = _seed_repo(db_session, "owner/repo-a")
    repo_b = _seed_repo(db_session, "owner/repo-b")

    assert analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo_a.id, commit_sha="samesha", pr_number=None, event="push",
    ) is True
    assert analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo_b.id, commit_sha="samesha", pr_number=None, event="push",
    ) is True

    assert db_session.query(AnalysisAttempt).count() == 2


# ── finish_attempt ───────────────────────────────────────────────────────────


def test_finish_attempt_deletes_row(db_session):
    """계약 3 — 정상 종료 시 행을 삭제해 orphan 오탐을 막는다."""
    # Contract 3 — normal completion deletes the row so it is not reported as an orphan.
    repo = _seed_repo(db_session)
    analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=7, event="pull_request",
    )
    assert db_session.query(AnalysisAttempt).count() == 1

    analysis_attempt_repo.finish_attempt(db_session, repo_id=repo.id, commit_sha="abc123")

    assert db_session.query(AnalysisAttempt).count() == 0


def test_finish_attempt_is_idempotent_when_row_absent(db_session):
    """계약 4 — 행이 없을 때 no-op (예외 없음).

    Contract 4 — a no-op when no row exists (must not raise). 파이프라인의 여러 정상 종료
    지점에서 호출되고, begin 이 False(동시 웹훅 패배)였던 경우에도 도달할 수 있다.
    Called from several normal-exit points, and reachable even when begin returned False.
    """
    repo = _seed_repo(db_session)

    # 예외가 나면 파이프라인 터미널 except 가 삼켜 정상 완료가 실패로 기록된다
    # An exception here would be swallowed by the pipeline's terminal except, logging a
    # successful run as a failure
    analysis_attempt_repo.finish_attempt(db_session, repo_id=repo.id, commit_sha="never-began")

    assert db_session.query(AnalysisAttempt).count() == 0


def test_finish_attempt_deletes_only_the_matching_row(db_session):
    """finish 는 대상 (repo_id, commit_sha) 만 지운다 — 진행 중인 다른 분석을 지우면 안 된다.

    finish must delete only the targeted (repo_id, commit_sha) — wiping other in-flight
    attempts would silently destroy the loss-detection evidence for concurrent analyses.
    """
    repo_a = _seed_repo(db_session, "owner/repo-a")
    repo_b = _seed_repo(db_session, "owner/repo-b")
    analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo_a.id, commit_sha="sha-1", pr_number=None, event="push",
    )
    analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo_a.id, commit_sha="sha-2", pr_number=None, event="push",
    )
    analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo_b.id, commit_sha="sha-1", pr_number=None, event="push",
    )

    analysis_attempt_repo.finish_attempt(db_session, repo_id=repo_a.id, commit_sha="sha-1")

    remaining = {(r.repo_id, r.commit_sha) for r in db_session.query(AnalysisAttempt).all()}
    assert remaining == {(repo_a.id, "sha-2"), (repo_b.id, "sha-1")}


def test_begin_after_finish_succeeds(db_session):
    """finish 후 동일 SHA 재시작이 가능해야 한다 (재분석·재전송 경로).

    A re-begin for the same SHA must succeed after finish — the UNIQUE row is gone, so a
    replayed/re-triggered analysis is not permanently locked out.
    """
    repo = _seed_repo(db_session)
    analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=None, event="push",
    )
    analysis_attempt_repo.finish_attempt(db_session, repo_id=repo.id, commit_sha="abc123")

    assert analysis_attempt_repo.begin_attempt(
        db_session, repo_id=repo.id, commit_sha="abc123", pr_number=None, event="push",
    ) is True
    assert db_session.query(AnalysisAttempt).count() == 1


# ── find_orphaned ────────────────────────────────────────────────────────────


def _insert_attempt(db, repo_id: int, commit_sha: str, minutes_ago: int) -> None:
    """started_at 을 명시 지정해 attempt 행 삽입 (시간 경과 시뮬레이션).
    Insert an attempt row with an explicit started_at (simulates elapsed time)."""
    db.add(AnalysisAttempt(
        repo_id=repo_id,
        commit_sha=commit_sha,
        pr_number=None,
        event="push",
        started_at=_now_naive() - timedelta(minutes=minutes_ago),
    ))
    db.commit()


def test_find_orphaned_returns_only_rows_older_than_threshold(db_session):
    """계약 5 — 임계치보다 오래된 행만 반환하고 최근 행은 제외한다.

    Contract 5 — return only rows older than the threshold; recent rows are still in-flight
    and must not be reported as lost (false-positive orphan).
    """
    repo = _seed_repo(db_session)
    _insert_attempt(db_session, repo.id, "old-60", minutes_ago=60)
    _insert_attempt(db_session, repo.id, "old-30", minutes_ago=30)
    _insert_attempt(db_session, repo.id, "recent-5", minutes_ago=5)
    _insert_attempt(db_session, repo.id, "recent-0", minutes_ago=0)

    orphans = analysis_attempt_repo.find_orphaned(db_session, older_than_minutes=15)

    assert [row.commit_sha for row in orphans] == ["old-60", "old-30"]


def test_find_orphaned_orders_by_started_at_ascending(db_session):
    """계약 5 — started_at 오름차순 (가장 오래 소실된 것부터)."""
    # Contract 5 — ascending by started_at (longest-lost first).
    repo = _seed_repo(db_session)
    # 삽입 순서를 의도적으로 뒤섞어 PK 순서와 started_at 순서를 분리 —
    # ORDER BY 누락 시 PK 순서로 우연히 통과하는 spurious pass 차단.
    # Insertion order is deliberately shuffled so PK order != started_at order — this blocks
    # the spurious pass where a missing ORDER BY happens to match insertion order.
    _insert_attempt(db_session, repo.id, "mid", minutes_ago=60)
    _insert_attempt(db_session, repo.id, "newest", minutes_ago=20)
    _insert_attempt(db_session, repo.id, "oldest", minutes_ago=180)

    orphans = analysis_attempt_repo.find_orphaned(db_session, older_than_minutes=15)

    assert [row.commit_sha for row in orphans] == ["oldest", "mid", "newest"]


def test_find_orphaned_returns_empty_when_nothing_is_stale(db_session):
    """계약 5 — 소실 후보가 없으면 빈 리스트 (None 아님)."""
    # Contract 5 — an empty list (not None) when nothing is stale.
    repo = _seed_repo(db_session)
    _insert_attempt(db_session, repo.id, "recent", minutes_ago=1)

    assert analysis_attempt_repo.find_orphaned(db_session, older_than_minutes=15) == []


def test_find_orphaned_respects_threshold_parameter(db_session):
    """계약 5 — older_than_minutes 가 실제 컷오프로 동작한다 (하드코딩 상수 아님).

    Contract 5 — older_than_minutes is the real cutoff, not a hardcoded constant. 동일 데이터에
    임계치만 바꿔 결과 집합이 달라지는지 검증.
    Same data, different thresholds must yield different result sets.
    """
    repo = _seed_repo(db_session)
    _insert_attempt(db_session, repo.id, "m-10", minutes_ago=10)
    _insert_attempt(db_session, repo.id, "m-45", minutes_ago=45)

    assert [r.commit_sha for r in
            analysis_attempt_repo.find_orphaned(db_session, older_than_minutes=5)] == ["m-45", "m-10"]
    assert [r.commit_sha for r in
            analysis_attempt_repo.find_orphaned(db_session, older_than_minutes=30)] == ["m-45"]
    assert analysis_attempt_repo.find_orphaned(db_session, older_than_minutes=120) == []


def test_find_orphaned_spans_repos(db_session):
    """계약 5 — 전 리포의 소실 후보를 반환한다 (운영 sweep 용도)."""
    # Contract 5 — returns stale rows across all repos (this feeds an operational sweep).
    repo_a = _seed_repo(db_session, "owner/repo-a")
    repo_b = _seed_repo(db_session, "owner/repo-b")
    _insert_attempt(db_session, repo_a.id, "sha-a", minutes_ago=90)
    _insert_attempt(db_session, repo_b.id, "sha-b", minutes_ago=120)

    orphans = analysis_attempt_repo.find_orphaned(db_session, older_than_minutes=15)

    assert [row.commit_sha for row in orphans] == ["sha-b", "sha-a"]
