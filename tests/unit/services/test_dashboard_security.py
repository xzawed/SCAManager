"""Cycle 73 F2 — dashboard_security 단위 테스트 (CI fix-up — patch coverage 80%+)."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.repository import Repository
from src.repositories import security_alert_log_repo
from src.services import dashboard_service


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


def test_dashboard_security_empty_db(db):
    """빈 DB → 0 카운트 + 빈 recent_pending + 분류 dict 5 키 모두 0."""
    result = dashboard_service.dashboard_security(db)
    assert result["total_alerts"] == 0
    assert result["pending_count"] == 0
    assert result["processed_count"] == 0
    assert result["recent_pending"] == []
    assert set(result["classification"].keys()) == {
        "false_positive", "used_in_tests", "actual_violation", "deferred", "unclassified",
    }


def test_dashboard_security_with_pending(db, repo):
    """pending alert 가 있으면 recent_pending 에 normalize 된 dict 포함."""
    security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=1,
        severity="note", rule_id="py/unused-import",
        ai_classification="false_positive", ai_confidence=0.95,
    )
    result = dashboard_service.dashboard_security(db)
    assert result["total_alerts"] == 1
    assert result["pending_count"] == 1
    assert len(result["recent_pending"]) == 1
    row = result["recent_pending"][0]
    assert row["alert_number"] == 1
    assert row["severity"] == "note"
    assert row["ai_classification"] == "false_positive"


def test_dashboard_security_kill_switch_flag(db, monkeypatch):
    """kill-switch 환경변수 활성 시 flag True."""
    monkeypatch.setenv("SECURITY_AUTO_PROCESS_DISABLED", "1")
    result = dashboard_service.dashboard_security(db)
    assert result["kill_switch_active"] is True


def test_dashboard_security_kill_switch_inactive_default(db, monkeypatch):
    """kill-switch 미설정 시 flag False (default 안전)."""
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)
    result = dashboard_service.dashboard_security(db)
    assert result["kill_switch_active"] is False
