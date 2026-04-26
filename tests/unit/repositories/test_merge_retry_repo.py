"""merge_retry_repo claim 의미론 단위 테스트 (Phase 12 T6).

T6 에서 추가된 함수들에 대한 테스트:
  - enqueue_or_bump()       — 신규 추가 또는 기존 행 업데이트
  - claim_batch()           — 처리 가능한 행 원자적 클레임
  - release_claim()         — 클레임 해제 및 재시도 대기 복귀
  - mark_succeeded()        — 성공 상태 마킹
  - mark_terminal()         — 영구 실패 상태 마킹
  - mark_expired()          — 만료 상태 마킹
  - mark_abandoned()        — 포기 상태 마킹
  - abandon_stale_for_pr()  — force-push 감지 시 오래된 SHA 행 포기 처리
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
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_retry import MergeRetryQueue
from src.models.repository import Repository
from src.repositories import merge_retry_repo


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """인메모리 SQLite DB 세션 — 각 테스트 후 폐기.
    In-memory SQLite session — discarded after each test.
    StaticPool 사용으로 SELECT + UPDATE 가 사실상 원자적 동작.
    Uses StaticPool so SELECT + UPDATE is effectively atomic.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    db_session.refresh(analysis)
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
    claimed_at: datetime | None = None,
    claim_token: str | None = None,
    attempts_count: int = 0,
) -> MergeRetryQueue:
    """MergeRetryQueue 행을 직접 삽입하는 헬퍼.
    Helper that inserts a MergeRetryQueue row directly.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = MergeRetryQueue(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        analysis_id=analysis_id,
        commit_sha=commit_sha,
        score=score,
        threshold_at_enqueue=threshold_at_enqueue,
        status=status,
        next_retry_at=next_retry_at if next_retry_at is not None else now,
        claimed_at=claimed_at,
        claim_token=claim_token,
        attempts_count=attempts_count,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 1. enqueue_or_bump()
# ---------------------------------------------------------------------------


def test_enqueue_or_bump_creates_new_row_when_none_exists(db_session):
    """기존 pending 행이 없으면 새 행을 생성하고 is_first_deferral=True 를 반환한다.
    Creates a new row and returns is_first_deferral=True when no pending row exists.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_new")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    result = merge_retry_repo.enqueue_or_bump(
        db_session,
        repo_full_name="owner/repo",
        pr_number=1,
        analysis_id=analysis.id,
        commit_sha="sha_new",
        score=80,
        threshold_at_enqueue=75,
        now=now,
    )

    assert result.is_first_deferral is True
    assert result.row.id is not None
    assert result.row.status == "pending"
    assert result.row.attempts_count == 0
    assert result.row.repo_full_name == "owner/repo"
    assert result.row.commit_sha == "sha_new"


def test_enqueue_or_bump_bumps_existing_pending_row(db_session):
    """동일 (repo, pr_number, commit_sha) pending 행이 있으면 업데이트하고 is_first_deferral=False 반환.
    Updates existing pending row and returns is_first_deferral=False when it exists.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_bump")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    old_next_retry = now - timedelta(minutes=30)

    # 기존 pending 행 삽입
    # Insert existing pending row.
    existing = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_bump",
        pr_number=5,
        next_retry_at=old_next_retry,
        attempts_count=2,
    )
    existing_id = existing.id

    result = merge_retry_repo.enqueue_or_bump(
        db_session,
        repo_full_name="owner/repo",
        pr_number=5,
        analysis_id=analysis.id,
        commit_sha="sha_bump",
        score=80,
        threshold_at_enqueue=75,
        now=now,
    )

    assert result.is_first_deferral is False
    # 동일 행이 업데이트되었어야 한다 — 새 행 생성 아님
    # Must update the same row, not create a new one.
    assert result.row.id == existing_id
    # next_retry_at 이 과거보다 미래로 갱신됨
    # next_retry_at updated beyond the old past value.
    assert result.row.next_retry_at > old_next_retry
    # attempts_count 는 유지 (bump 은 시도 횟수 증가 아님)
    # attempts_count preserved (bump does not increment).
    assert result.row.attempts_count == 2


def test_enqueue_or_bump_ignores_non_pending_rows(db_session):
    """succeeded 행은 '기존 행'으로 간주하지 않아 새 행을 생성한다.
    Does not treat succeeded rows as existing — creates a new pending row.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_done")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # succeeded 상태 행 삽입
    # Insert a succeeded row.
    _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_done",
        pr_number=7,
        status="succeeded",
    )

    result = merge_retry_repo.enqueue_or_bump(
        db_session,
        repo_full_name="owner/repo",
        pr_number=7,
        analysis_id=analysis.id,
        commit_sha="sha_done",
        score=80,
        threshold_at_enqueue=75,
        now=now,
    )

    # succeeded 행 무시하고 새 pending 행 생성
    # Ignores succeeded row and creates new pending row.
    assert result.is_first_deferral is True
    assert result.row.status == "pending"
    # DB 에 2행 존재 (succeeded + new pending)
    # DB now has 2 rows (succeeded + new pending).
    total = db_session.query(MergeRetryQueue).count()
    assert total == 2


def test_enqueue_or_bump_sets_notify_chat_id(db_session):
    """notify_chat_id 가 새 행에 저장된다.
    notify_chat_id is stored in the new row.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_chat")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    result = merge_retry_repo.enqueue_or_bump(
        db_session,
        repo_full_name="owner/repo",
        pr_number=9,
        analysis_id=analysis.id,
        commit_sha="sha_chat",
        score=80,
        threshold_at_enqueue=75,
        notify_chat_id="-100999",
        now=now,
    )

    assert result.row.notify_chat_id == "-100999"


# ---------------------------------------------------------------------------
# 2. claim_batch()
# ---------------------------------------------------------------------------


def test_claim_batch_claims_due_rows(db_session):
    """next_retry_at <= now 인 pending 행을 클레임한다.
    claim_batch() claims pending rows where next_retry_at <= now.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_due")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    past = now - timedelta(minutes=5)

    row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_due",
        next_retry_at=past,
    )

    claimed = merge_retry_repo.claim_batch(db_session, now=now)

    assert len(claimed) == 1
    assert claimed[0].id == row.id
    # 클레임 후 claimed_at 이 설정되어야 한다
    # claimed_at must be set after claiming.
    assert claimed[0].claimed_at is not None
    assert claimed[0].claim_token is not None


def test_claim_batch_skips_future_rows(db_session):
    """next_retry_at > now 인 행은 클레임하지 않는다.
    claim_batch() skips rows where next_retry_at > now.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_future")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    future = now + timedelta(hours=1)

    _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_future",
        next_retry_at=future,
    )

    claimed = merge_retry_repo.claim_batch(db_session, now=now)

    assert claimed == []


def test_claim_batch_skips_recently_claimed_rows(db_session):
    """최근 claimed_at 이 있는 행 (stale 기준 미만) 은 재클레임하지 않는다.
    claim_batch() skips rows with recent claimed_at (not yet stale).
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_recent")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    past = now - timedelta(minutes=1)

    # 최근에 클레임된 행 — stale 기준(5분) 미달
    # Recently claimed row — within stale threshold (5 min).
    _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_recent",
        next_retry_at=past,
        claimed_at=now - timedelta(seconds=60),  # 1분 전 — 5분 미만
        claim_token="old-token",
    )

    # stale_after_seconds=300 (5분) 기본값 사용
    # Uses default stale_after_seconds=300 (5 min).
    claimed = merge_retry_repo.claim_batch(db_session, now=now, stale_after_seconds=300)

    assert claimed == []


def test_claim_batch_reclaims_stale_claims(db_session):
    """stale 기준 초과한 오래된 클레임은 재클레임한다.
    claim_batch() reclaims rows whose claimed_at is older than stale threshold.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_stale")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    past = now - timedelta(minutes=10)
    stale_claimed_at = now - timedelta(seconds=400)  # 400초 전 — 5분 초과

    row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_stale",
        next_retry_at=past,
        claimed_at=stale_claimed_at,
        claim_token="stale-token",
    )

    claimed = merge_retry_repo.claim_batch(db_session, now=now, stale_after_seconds=300)

    assert len(claimed) == 1
    assert claimed[0].id == row.id
    # claim_token 이 새 값으로 갱신됨
    # claim_token updated to a new value.
    assert claimed[0].claim_token != "stale-token"


def test_claim_batch_increments_attempts_count(db_session):
    """클레임 시 attempts_count 가 0 → 1 로 증가한다.
    claim_batch() increments attempts_count from 0 to 1 on first claim.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_inc")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    past = now - timedelta(minutes=5)

    row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_inc",
        next_retry_at=past,
        attempts_count=0,
    )
    assert row.attempts_count == 0

    claimed = merge_retry_repo.claim_batch(db_session, now=now)

    assert len(claimed) == 1
    # 첫 번째 클레임 후 attempts_count = 1
    # attempts_count = 1 after first claim.
    assert claimed[0].attempts_count == 1


def test_claim_batch_only_ids_filter(db_session):
    """only_ids 파라미터로 특정 ID 만 클레임한다.
    claim_batch() with only_ids claims only the specified rows.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_ids1")
    analysis2 = _seed_analysis(db_session, commit_sha="sha_ids2")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    past = now - timedelta(minutes=5)

    row1 = _make_queue_row(
        db_session, analysis_id=analysis.id, commit_sha="sha_ids1", pr_number=20, next_retry_at=past
    )
    _make_queue_row(
        db_session, analysis_id=analysis2.id, commit_sha="sha_ids2", pr_number=21, next_retry_at=past
    )

    # row1 만 클레임 요청
    # Request only row1 to be claimed.
    claimed = merge_retry_repo.claim_batch(db_session, now=now, only_ids=[row1.id])

    assert len(claimed) == 1
    assert claimed[0].id == row1.id


# ---------------------------------------------------------------------------
# 3. release_claim()
# ---------------------------------------------------------------------------


def test_release_claim_clears_claimed_fields(db_session):
    """release_claim 은 claimed_at/claim_token 을 None 으로 초기화하고 next_retry_at 을 갱신한다.
    release_claim() clears claimed_at/claim_token and updates next_retry_at.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_rel")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_rel",
        next_retry_at=now - timedelta(minutes=5),
        claimed_at=now - timedelta(seconds=30),
        claim_token="some-token",
    )

    future_retry = now + timedelta(minutes=10)
    result = merge_retry_repo.release_claim(
        db_session,
        row.id,
        next_retry_at=future_retry,
        last_failure_reason="unstable_ci",
        last_detail_message="CI still running",
        now=now,
    )

    assert result is True
    db_session.refresh(row)
    assert row.claimed_at is None
    assert row.claim_token is None
    assert row.next_retry_at == future_retry
    assert row.last_failure_reason == "unstable_ci"
    assert row.last_detail_message == "CI still running"


def test_release_claim_returns_false_for_missing_row(db_session):
    """존재하지 않는 row_id 에 대해 False 반환.
    release_claim() returns False for a non-existent row_id.
    """
    result = merge_retry_repo.release_claim(
        db_session,
        9999,
        next_retry_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    assert result is False


# ---------------------------------------------------------------------------
# 4. Status markers
# ---------------------------------------------------------------------------


def test_mark_succeeded_updates_status(db_session):
    """mark_succeeded 는 status 를 'succeeded' 로 변경하고 True 반환.
    mark_succeeded() sets status to 'succeeded' and returns True.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_succ")
    row = _make_queue_row(db_session, analysis_id=analysis.id, commit_sha="sha_succ")

    result = merge_retry_repo.mark_succeeded(db_session, row.id)

    assert result is True
    db_session.refresh(row)
    assert row.status == "succeeded"
    assert row.claimed_at is None
    assert row.claim_token is None


def test_mark_succeeded_returns_false_for_missing(db_session):
    """존재하지 않는 row_id 에 False 반환.
    mark_succeeded() returns False for non-existent row_id.
    """
    result = merge_retry_repo.mark_succeeded(db_session, 9999)
    assert result is False


def test_mark_terminal_updates_status(db_session):
    """mark_terminal 은 status 를 'failed_terminal' 로 변경하고 reason 저장.
    mark_terminal() sets status to 'failed_terminal' and stores reason.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_term")
    row = _make_queue_row(db_session, analysis_id=analysis.id, commit_sha="sha_term")

    result = merge_retry_repo.mark_terminal(
        db_session, row.id, reason="permission_denied"
    )

    assert result is True
    db_session.refresh(row)
    assert row.status == "failed_terminal"
    assert row.last_failure_reason == "permission_denied"
    assert row.claimed_at is None


def test_mark_expired_updates_status(db_session):
    """mark_expired 는 status 를 'expired' 로 변경한다.
    mark_expired() sets status to 'expired'.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_exp")
    row = _make_queue_row(db_session, analysis_id=analysis.id, commit_sha="sha_exp")

    result = merge_retry_repo.mark_expired(db_session, row.id, reason="sha_drift")

    assert result is True
    db_session.refresh(row)
    assert row.status == "expired"
    assert row.last_failure_reason == "sha_drift"


def test_mark_abandoned_updates_status(db_session):
    """mark_abandoned 는 status 를 'abandoned' 로 변경하고 reason 저장.
    mark_abandoned() sets status to 'abandoned' and stores reason.
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_abd")
    row = _make_queue_row(db_session, analysis_id=analysis.id, commit_sha="sha_abd")

    result = merge_retry_repo.mark_abandoned(
        db_session, row.id, reason="max_attempts_exceeded"
    )

    assert result is True
    db_session.refresh(row)
    assert row.status == "abandoned"
    assert row.last_failure_reason == "max_attempts_exceeded"
    assert row.claimed_at is None


# ---------------------------------------------------------------------------
# 5. abandon_stale_for_pr()
# ---------------------------------------------------------------------------


def test_abandon_stale_for_pr_marks_old_sha_rows(db_session):
    """force-push 감지 시 이전 SHA 의 pending 행만 abandoned 로 변경한다.
    abandon_stale_for_pr() marks only old-SHA pending rows as abandoned on force-push.
    """
    analysis_old = _seed_analysis(db_session, commit_sha="sha_old")
    analysis_new = _seed_analysis(db_session, commit_sha="sha_new_curr")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 이전 SHA 행 — abandoned 되어야 함
    # Old SHA row — should be abandoned.
    old_row = _make_queue_row(
        db_session,
        analysis_id=analysis_old.id,
        commit_sha="sha_old",
        pr_number=10,
    )
    # 새 SHA 행 — 유지되어야 함
    # New SHA row — should remain pending.
    new_row = _make_queue_row(
        db_session,
        analysis_id=analysis_new.id,
        commit_sha="sha_new_curr",
        pr_number=10,
    )

    count = merge_retry_repo.abandon_stale_for_pr(
        db_session,
        repo_full_name="owner/repo",
        pr_number=10,
        current_sha="sha_new_curr",
        reason="sha_drift",
        now=now,
    )

    assert count == 1
    db_session.refresh(old_row)
    db_session.refresh(new_row)
    assert old_row.status == "abandoned"
    assert old_row.last_failure_reason == "sha_drift"
    # 새 SHA 행은 pending 유지
    # New SHA row remains pending.
    assert new_row.status == "pending"


def test_abandon_stale_for_pr_ignores_non_pending(db_session):
    """비-pending 상태(succeeded 등) 행은 abandon_stale_for_pr 에서 무시한다.
    abandon_stale_for_pr() ignores non-pending rows (e.g. succeeded).
    """
    analysis = _seed_analysis(db_session, commit_sha="sha_done_s")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # succeeded 상태 이전 SHA 행
    # Succeeded old-SHA row.
    succeeded_row = _make_queue_row(
        db_session,
        analysis_id=analysis.id,
        commit_sha="sha_done_s",
        pr_number=11,
        status="succeeded",
    )

    count = merge_retry_repo.abandon_stale_for_pr(
        db_session,
        repo_full_name="owner/repo",
        pr_number=11,
        current_sha="sha_new_current",
        now=now,
    )

    assert count == 0
    db_session.refresh(succeeded_row)
    # succeeded 상태 유지
    # Remains succeeded.
    assert succeeded_row.status == "succeeded"


def test_abandon_stale_for_pr_returns_zero_when_no_stale(db_session):
    """오래된 SHA 의 pending 행이 없으면 0 을 반환한다.
    abandon_stale_for_pr() returns 0 when there are no stale pending rows.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    count = merge_retry_repo.abandon_stale_for_pr(
        db_session,
        repo_full_name="owner/repo",
        pr_number=99,
        current_sha="sha_only",
        now=now,
    )

    assert count == 0
