"""Cycle 73 F1 — security_alert_log_repo 단위 테스트 (upsert + decision + counts)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.repository import Repository
from src.repositories import security_alert_log_repo


@pytest.fixture
def db() -> Session:
    """in-memory SQLite engine — 단일 테스트 격리."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session_ = sessionmaker(bind=engine)
    session = Session_()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def repo(db: Session) -> Repository:
    r = Repository(full_name="owner/test", user_id=None)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def test_upsert_alert_log_inserts_new(db, repo):
    """신규 alert 는 INSERT — pending 상태로 저장."""
    log = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=42,
        severity="note", rule_id="py/unused-import",
    )
    assert log.id is not None
    assert log.alert_number == 42
    assert log.user_decision is None  # pending


def test_upsert_alert_log_updates_existing(db, repo):
    """동일 (repo, alert_type, alert_number) 재호출 = AI 분류만 갱신, user_decision 보존."""
    log1 = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=42,
        severity="note", rule_id="py/unused-import",
    )
    security_alert_log_repo.record_user_decision(
        db, log_id=log1.id, user_id=1, decision="accept_ai",
    )
    # 재 upsert (AI 재분류) — user_decision 보존 의무
    log2 = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=42,
        ai_classification="false_positive", ai_confidence=0.95,
    )
    assert log1.id == log2.id  # 동일 row
    assert log2.ai_classification == "false_positive"
    assert log2.user_decision == "accept_ai"  # 보존


def test_record_user_decision_returns_none_on_missing(db):
    """존재하지 않는 log_id 시 None 반환 (HTTP 404 영역)."""
    result = security_alert_log_repo.record_user_decision(
        db, log_id=9999, user_id=1, decision="accept_ai",
    )
    assert result is None


def test_list_pending_filters_decided(db, repo):
    """user_decision NOT NULL 인 row 는 pending list 에서 제외."""
    log_pending = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=1,
    )
    log_decided = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=2,
    )
    security_alert_log_repo.record_user_decision(
        db, log_id=log_decided.id, user_id=1, decision="accept_ai",
    )
    pending = security_alert_log_repo.list_pending(db)
    assert len(pending) == 1
    assert pending[0].id == log_pending.id


def test_count_by_classification_includes_pending(db, repo):
    """카운트 dict — total + pending + 분류별 합계 보장."""
    security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=1,
        ai_classification="false_positive",
    )
    security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=2,
        ai_classification="used_in_tests",
    )
    security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=3,
    )  # ai_classification = None → "unclassified"
    counts = security_alert_log_repo.count_by_classification(db)
    assert counts["total"] == 3
    assert counts["pending"] == 3  # user_decision = None
    assert counts.get("false_positive") == 1
    assert counts.get("used_in_tests") == 1
    assert counts.get("unclassified") == 1
