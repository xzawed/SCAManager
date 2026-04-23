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
