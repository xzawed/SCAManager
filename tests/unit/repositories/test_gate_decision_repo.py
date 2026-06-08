"""gate_decision_repo 단위 테스트."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

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
