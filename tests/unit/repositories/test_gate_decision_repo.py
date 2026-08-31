"""gate_decision_repo 단위 테스트."""
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
from src.models.gate_decision import GateDecision
from src.models.repository import Repository
from src.repositories import gate_decision_repo


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


def _seed_analysis(db_session) -> Analysis:
    repo = Repository(full_name="o/r")
    db_session.add(repo)
    db_session.commit()
    a = Analysis(repo_id=repo.id, commit_sha="abc123", score=80, grade="B")
    db_session.add(a)
    db_session.commit()
    return a


def test_upsert_insert_new_decision(db_session):
    a = _seed_analysis(db_session)
    rec = gate_decision_repo.upsert(db_session, a.id, "approve", "auto", "alice")
    assert rec.decision == "approve"
    assert rec.mode == "auto"
    assert db_session.query(GateDecision).count() == 1


def test_upsert_updates_existing(db_session):
    a = _seed_analysis(db_session)
    gate_decision_repo.upsert(db_session, a.id, "skip", "auto")
    gate_decision_repo.upsert(db_session, a.id, "approve", "semi-auto", "bob")
    # 동일 analysis_id 로 업데이트 — 중복 INSERT 금지
    assert db_session.query(GateDecision).count() == 1
    rec = gate_decision_repo.find_by_analysis_id(db_session, a.id)
    assert rec.decision == "approve"
    assert rec.mode == "semi-auto"
    assert rec.decided_by == "bob"


def test_find_by_analysis_id_not_found(db_session):
    assert gate_decision_repo.find_by_analysis_id(db_session, 9999) is None


def test_claim_decision_first_wins(db_session):
    """claim_decision: 최초 claim 은 True 반환 + 결정 INSERT (#11 원자적 first-writer)."""
    a = _seed_analysis(db_session)
    won = gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual", "alice")
    assert won is True
    rec = gate_decision_repo.find_by_analysis_id(db_session, a.id)
    assert rec.decision == "approve"
    assert rec.mode == "manual"
    assert rec.decided_by == "alice"
    assert db_session.query(GateDecision).count() == 1


def test_claim_decision_duplicate_loses_no_flip(db_session):
    """claim_decision: 동일 analysis_id 2차 claim 은 False(UNIQUE 위반 흡수) + 결정 뒤집기 차단.

    리플레이/동시 패자가 부수효과를 skip 하도록 False 를 반환하며, 기존 결정은 변경되지 않는다.
    """
    a = _seed_analysis(db_session)
    assert gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual", "alice") is True
    # 2차 claim (다른 결정으로 뒤집기 시도) — UNIQUE(analysis_id) 위반 → False
    lost = gate_decision_repo.claim_decision(db_session, a.id, "reject", "manual", "mallory")
    assert lost is False
    # 중복 INSERT 없음 + 최초 결정 보존 (뒤집기 차단)
    assert db_session.query(GateDecision).count() == 1
    rec = gate_decision_repo.find_by_analysis_id(db_session, a.id)
    assert rec.decision == "approve"
    assert rec.decided_by == "alice"


def test_claim_decision_absorbs_non_unique_integrity_error(db_session):
    """correctness 회귀 가드: claim_decision 의 broad `except IntegrityError` 는 UNIQUE 외
    NOT NULL/FK 위반도 흡수해 graceful False 를 반환한다(크래시 아님). 호출자는 호출 전
    analysis 존재를 보장할 책임이 있다(docstring 명시). 사이클 165 회고 correctness P1-1.

    analysis_id=None → NOT NULL(nullable=False) 위반 → IntegrityError → 흡수 → False.
    (UNIQUE 충돌이 아닌 IntegrityError 도 동일 경로로 흡수됨을 봉인.)
    """
    won = gate_decision_repo.claim_decision(db_session, None, "approve", "manual", "alice")
    assert won is False
    # 아무 행도 영속되지 않아야 한다 (rollback)
    assert db_session.query(GateDecision).count() == 0


# ── 게시 상태 · in-flight 클레임 (#1504 R2) ──────────────────────────────────
#
# 🔴 오늘의 결함: `claim_decision` 이 **먼저 커밋**되고 그 다음 `post_github_review` 가 돈다.
#    POST 가 전송 오류로 실패하면 claim 은 남고 리뷰는 없고, 같은 버튼을 다시 눌러도
#    `claim_decision` 이 False 를 돌려 부수효과가 skip 된다 — **재시도 수단이 없다.**
#    콜백 HMAC 은 `gate:{analysis_id}` 만 서명하고 만료가 없어 그 버튼은 영원히 살아 있다.
#
# 🔴 `state == 'pending_post'` 는 **잠금이 아니다**(Grok claim-review `01a05767`).
#    두 클릭이 둘 다 그것을 보고 둘 다 POST 하면 **중복 리뷰**가 생긴다 — 원래 가드가
#    막으려던 바로 그것이다. 그래서 POST 직전에 **배타적 in-flight 클레임**이 필요하다.
#
# 🔴 리스를 `decided_at` 으로 잡으면 안 된다. HMAC 이 만료되지 않으므로 몇 시간 뒤 클릭은
#    `decided_at` 이 이미 낡았고, 그러면 리스가 **진입하는 순간 만료로 보여** CAS 가 무력해진다 —
#    이 버그가 다루는 바로 그 늦은 클릭 경로에서. 별도 `post_claimed_at` 을 둔다.
#    집 패턴은 `merge_retry_repo::def claim_batch` 다.

_PENDING, _POSTED = "pending_post", "posted"


def test_claim_decision_starts_pending_post(db_session):
    """🔴 클레임은 「결정했다」이지 「게시했다」가 아니다."""
    a = _seed_analysis(db_session)
    assert gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual") is True
    row = gate_decision_repo.find_by_analysis_id(db_session, a.id)
    assert row.state == _PENDING, f"클레임 직후 상태가 {row.state!r} — 아직 게시 전이다"
    assert row.post_claimed_at is None, "in-flight 클레임이 미리 잡혀 있다"


def test_upsert_records_posted(db_session):
    """🔴 자동 경로는 **게시 성공 뒤에** 기록한다 — 그 행은 재시도 대상이 아니다.

    `server_default` 에 기대지 않고 **명시**한다. ORM 속성을 안 채우면 INSERT 가 NULL 을
    보내고, 그러면 새 재시도 갈래가 그 행을 「미게시」로 읽는다.
    """
    a = _seed_analysis(db_session)
    row = gate_decision_repo.upsert(db_session, a.id, "approve", "auto")
    assert row.state == _POSTED, f"자동 경로가 {row.state!r} 로 기록했다 — 재시도 대상이 된다"


def test_post_attempt_is_claimed_once(db_session):
    """🔴 **배타적** in-flight 클레임 — 동시 재클릭 둘 중 하나만 POST 한다."""
    a = _seed_analysis(db_session)
    gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual")
    first = gate_decision_repo.claim_post_attempt(db_session, a.id)
    second = gate_decision_repo.claim_post_attempt(db_session, a.id)
    assert first is not None, "첫 클레임이 실패했다"
    assert second is None, "두 번째도 클레임됐다 — 중복 리뷰가 난다"


def test_post_attempt_returns_the_claimed_decision(db_session):
    """🔴 재시도는 **클레임된 결정**을 게시한다 — 새 클릭의 결정이 아니다.

    HMAC 은 `gate:{analysis_id}` 만 서명한다. 재시도가 새 클릭의 결정을 게시하면
    `claim_decision` 이 막던 approve→reject **뒤집기**가 되살아난다.
    """
    a = _seed_analysis(db_session)
    gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual")
    row = gate_decision_repo.claim_post_attempt(db_session, a.id)
    assert row.decision == "approve", f"클레임된 결정이 {row.decision!r} 로 바뀌었다"


def test_a_posted_decision_is_never_reclaimed(db_session):
    """🔴 게시된 결정은 재시도 대상이 아니다 — 리스가 아무리 낡아도."""
    a = _seed_analysis(db_session)
    gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual")
    gate_decision_repo.claim_post_attempt(db_session, a.id)
    gate_decision_repo.mark_posted(db_session, a.id)
    ancient = datetime.now(timezone.utc) + timedelta(days=365)
    assert gate_decision_repo.claim_post_attempt(db_session, a.id, now=ancient) is None, (
        "게시된 결정이 다시 클레임됐다 — 중복 리뷰"
    )


def test_a_stale_claim_is_reclaimable(db_session):
    """🔴 클레임한 프로세스가 죽으면 그 행이 영원히 갇히면 안 된다 — 리스로 되찾는다."""
    a = _seed_analysis(db_session)
    gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual")
    assert gate_decision_repo.claim_post_attempt(db_session, a.id) is not None
    later = datetime.now(timezone.utc) + timedelta(seconds=gate_decision_repo.POST_LEASE_SECONDS + 1)
    assert gate_decision_repo.claim_post_attempt(db_session, a.id, now=later) is not None, (
        "리스가 지났는데 되찾지 못했다 — 죽은 클레임이 버튼을 영구히 막는다"
    )


def test_a_fresh_claim_is_not_reclaimable(db_session):
    """🔴 부정 통제 — 리스 안에서는 되찾히면 안 된다. 없으면 위 시험이 「항상 클레임」과 같다."""
    a = _seed_analysis(db_session)
    gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual")
    gate_decision_repo.claim_post_attempt(db_session, a.id)
    within = datetime.now(timezone.utc) + timedelta(seconds=gate_decision_repo.POST_LEASE_SECONDS - 1)
    assert gate_decision_repo.claim_post_attempt(db_session, a.id, now=within) is None


def test_release_lets_the_next_click_retry_immediately(db_session):
    """🔴 알려진 실패(전송 오류·head 이동)는 리스를 풀어 준다 — 사람을 기다리게 하지 않는다."""
    a = _seed_analysis(db_session)
    gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual")
    gate_decision_repo.claim_post_attempt(db_session, a.id)
    gate_decision_repo.release_post_claim(db_session, a.id)
    assert gate_decision_repo.claim_post_attempt(db_session, a.id) is not None


def test_release_does_not_resurrect_a_posted_decision(db_session):
    """🔴 부정 통제 — 게시 뒤 release 가 불려도 상태는 `posted` 로 남는다."""
    a = _seed_analysis(db_session)
    gate_decision_repo.claim_decision(db_session, a.id, "approve", "manual")
    gate_decision_repo.claim_post_attempt(db_session, a.id)
    gate_decision_repo.mark_posted(db_session, a.id)
    gate_decision_repo.release_post_claim(db_session, a.id)
    row = gate_decision_repo.find_by_analysis_id(db_session, a.id)
    assert row.state == _POSTED, f"게시된 결정이 {row.state!r} 로 되돌아갔다"
    assert gate_decision_repo.claim_post_attempt(db_session, a.id) is None
