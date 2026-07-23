"""merge_retry_repo 소유권 CAS 단위 테스트 (종합감사 P1-5, 2026-07-23).

merge_retry_repo ownership-CAS unit tests (comprehensive audit P1-5).

배경: process_pending_retries 워커가 행을 claim(claim_token=T1)한 뒤 처리가 stale 임계(300s)를
넘기면 다른 워커가 그 행을 재클레임(claim_token=T2)한다. 원래 워커가 뒤늦게 write-back(mark_*/
release_claim)하면 T2 워커의 결과를 clobber 하거나 종결 행을 재시도로 부활시킨다. 수정 = 모든
write-back 에 expected_claim_token CAS 조건을 걸어, 토큰 불일치 시 0행 매치 → no-op(False) 되게 한다.

Background: if a worker's claim goes stale (>300s) another worker reclaims the row with a new token.
The original worker's late write-back must become a no-op — this file pins that CAS behavior.
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
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_retry import MergeRetryQueue
from src.models.repository import Repository
from src.repositories import merge_retry_repo


@pytest.fixture
def db_session():
    """인메모리 SQLite 세션. / In-memory SQLite session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_claimed_row(db_session, *, claim_token: str) -> MergeRetryQueue:
    """claim_token 이 걸린(=claimed) pending 행을 시드한다.
    Seed a pending row that is already claimed with claim_token.
    """
    repo = Repository(full_name="owner/repo")
    db_session.add(repo)
    db_session.commit()
    analysis = Analysis(repo_id=repo.id, commit_sha="abc123", score=80, grade="B", result={})
    db_session.add(analysis)
    db_session.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = MergeRetryQueue(
        repo_full_name="owner/repo",
        pr_number=1,
        analysis_id=analysis.id,
        commit_sha="abc123",
        score=80,
        threshold_at_enqueue=75,
        status="pending",
        next_retry_at=now,
        claimed_at=now,
        claim_token=claim_token,
        attempts_count=1,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def _fresh(db_session, row_id: int) -> MergeRetryQueue:
    """identity-map 우회 재조회 — write-back 후 실제 DB 상태 확인용.
    Re-fetch bypassing the identity map — to read the true post-write DB state.
    """
    db_session.expire_all()
    return db_session.query(MergeRetryQueue).filter(MergeRetryQueue.id == row_id).first()


# ---------------------------------------------------------------------------
# release_claim CAS
# ---------------------------------------------------------------------------


def test_release_claim_matching_token_succeeds(db_session):
    """expected_claim_token 이 일치하면 해제하고 True 반환.
    Matching token → release succeeds (True), claim cleared.
    """
    row = _seed_claimed_row(db_session, claim_token="T1")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    ok = merge_retry_repo.release_claim(
        db_session, row.id, next_retry_at=now + timedelta(seconds=30),
        last_failure_reason="transient", expected_claim_token="T1",
    )

    assert ok is True
    after = _fresh(db_session, row.id)
    assert after.claim_token is None
    assert after.claimed_at is None
    assert after.last_failure_reason == "transient"


def test_release_claim_stale_token_is_noop(db_session):
    """재클레임으로 토큰이 T2 로 바뀐 뒤 원래 워커가 T1 로 release 하면 no-op(False) — clobber 차단.
    After reclaim (token T2), the original worker's T1 release is a no-op (False) — no clobber.
    """
    # 다른 워커가 이미 재클레임: DB 의 claim_token = T2
    # Another worker already reclaimed: DB claim_token = T2
    row = _seed_claimed_row(db_session, claim_token="T2")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    ok = merge_retry_repo.release_claim(
        db_session, row.id, next_retry_at=now + timedelta(seconds=30),
        last_failure_reason="transient", expected_claim_token="T1",  # 원래 워커의 stale 토큰
    )

    assert ok is False
    after = _fresh(db_session, row.id)
    # T2 워커의 클레임은 그대로 보존 — 원래 워커가 되돌리지 못함
    # T2 worker's claim is preserved — the original worker could not revert it
    assert after.claim_token == "T2"
    assert after.claimed_at is not None
    assert after.last_failure_reason is None


def test_release_claim_without_token_is_backward_compatible(db_session):
    """expected_claim_token 미전달 시 CAS 없이 기존 동작 — True.
    Omitting expected_claim_token keeps legacy behavior (no CAS) — True.
    """
    row = _seed_claimed_row(db_session, claim_token="T1")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    ok = merge_retry_repo.release_claim(
        db_session, row.id, next_retry_at=now + timedelta(seconds=30),
    )

    assert ok is True
    assert _fresh(db_session, row.id).claim_token is None


# ---------------------------------------------------------------------------
# mark_* CAS (succeeded / terminal / expired / abandoned)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fn_name,kwargs,expect_status",
    [
        ("mark_succeeded", {}, "succeeded"),
        ("mark_terminal", {"reason": "permission"}, "failed_terminal"),
        ("mark_expired", {}, "expired"),
        ("mark_abandoned", {"reason": "sha_drift"}, "abandoned"),
    ],
)
def test_mark_matching_token_succeeds(db_session, fn_name, kwargs, expect_status):
    """토큰 일치 시 마킹 성공 — status 전이 + True.
    Matching token → mark succeeds — status transitions + True.
    """
    row = _seed_claimed_row(db_session, claim_token="T1")
    fn = getattr(merge_retry_repo, fn_name)

    ok = fn(db_session, row.id, expected_claim_token="T1", **kwargs)

    assert ok is True
    assert _fresh(db_session, row.id).status == expect_status


@pytest.mark.parametrize(
    "fn_name,kwargs",
    [
        ("mark_succeeded", {}),
        ("mark_terminal", {"reason": "permission"}),
        ("mark_expired", {}),
        ("mark_abandoned", {"reason": "sha_drift"}),
    ],
)
def test_mark_stale_token_is_noop(db_session, fn_name, kwargs):
    """재클레임(T2) 후 원래 워커(T1)의 마킹은 no-op — 종결 상태 clobber·재시도 부활 차단.
    After reclaim (T2), the original worker's (T1) mark is a no-op — no terminal-state clobber.
    """
    row = _seed_claimed_row(db_session, claim_token="T2")
    fn = getattr(merge_retry_repo, fn_name)

    ok = fn(db_session, row.id, expected_claim_token="T1", **kwargs)

    assert ok is False
    after = _fresh(db_session, row.id)
    # 여전히 pending + T2 클레임 — 종결로 덮이지 않음
    # Still pending + T2 claim — not overwritten to a terminal state
    assert after.status == "pending"
    assert after.claim_token == "T2"


def test_mark_without_token_is_backward_compatible(db_session):
    """expected_claim_token 미전달 시 CAS 없이 마킹 — True (기존 호출부 회귀 방지).
    Omitting the token keeps legacy behavior — True (protects pre-existing callers).
    """
    row = _seed_claimed_row(db_session, claim_token="T1")

    ok = merge_retry_repo.mark_succeeded(db_session, row.id)

    assert ok is True
    assert _fresh(db_session, row.id).status == "succeeded"
