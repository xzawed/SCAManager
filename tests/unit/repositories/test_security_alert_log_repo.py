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


def test_upsert_alert_log_updates_existing_and_keeps_user_decision(db, repo):
    """동일 (repo, alert_type, alert_number) 재호출 = 같은 행 · 심각도 갱신 · user_decision 보존."""
    log1 = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=42,
        severity="note", rule_id="py/unused-import",
    )
    log1.user_decision = "accept_ai"  # 결정을 쓰는 제품 코드는 없다 — 행에 직접 심는다 / no writer: plant it
    db.commit()
    log2 = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=42, severity="error",
    )
    assert log1.id == log2.id  # 동일 row
    assert log2.severity == "error"
    assert log2.user_decision == "accept_ai"  # 보존


def test_list_pending_filters_decided(db, repo):
    """user_decision NOT NULL 인 row 는 pending list 에서 제외."""
    log_pending = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=1,
    )
    log_decided = security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=2,
    )
    log_decided.user_decision = "accept_ai"
    db.commit()
    pending = security_alert_log_repo.list_pending(db)
    assert [row.id for row in pending] == [log_pending.id]


# ── GitHub 쪽 상태 — 열림 · 닫힘 대조 (회고 원장 L05 P1-35) ──────────────────────────────
# The alert's state on GitHub: open alerts are upserted, alerts missing from a complete open list are closed.

def _seed(db, repo, numbers, alert_type="code_scanning"):
    return [security_alert_log_repo.upsert_alert_log(db, repo_id=repo.id, alert_type=alert_type, alert_number=n)
            for n in numbers]


def test_a_new_alert_is_open_on_github(db, repo):
    """🔴 폴링이 본 alert 은 GitHub 에서 열린 것이다."""
    (log,) = _seed(db, repo, [7])
    assert log.github_state == security_alert_log_repo.OPEN


def test_close_missing_alerts_closes_only_the_absent_open_rows(db, repo):
    """🔴 끝까지 받은 열린 목록에 없는 행만 닫는다 — 같은 repo · 같은 종류만(다른 종류 · 다른 repo 는 그대로)."""
    _seed(db, repo, [1, 2, 3])
    _seed(db, repo, [1], alert_type="secret_scanning")
    other = Repository(full_name="owner/other", user_id=None)
    db.add(other)
    db.commit()
    _seed(db, other, [1])
    closed = security_alert_log_repo.close_missing_alerts(
        db, repo_id=repo.id, alert_type="code_scanning", open_numbers={2})
    assert closed == 2
    states = {(r.repo_id, r.alert_type, r.alert_number): r.github_state
              for r in db.query(security_alert_log_repo.SecurityAlertProcessLog).all()}
    assert states == {
        (repo.id, "code_scanning", 1): "closed", (repo.id, "code_scanning", 2): "open",
        (repo.id, "code_scanning", 3): "closed", (repo.id, "secret_scanning", 1): "open",
        (other.id, "code_scanning", 1): "open",
    }


def test_an_empty_complete_list_closes_every_open_row_of_that_kind(db, repo):
    """🔴 열린 alert 이 0개라는 완전한 목록 = 그 종류는 모두 닫혔다."""
    _seed(db, repo, [1, 2])
    assert security_alert_log_repo.close_missing_alerts(
        db, repo_id=repo.id, alert_type="code_scanning", open_numbers=set()) == 2


def test_a_closed_alert_that_reappears_is_open_again(db, repo):
    """🔴 GitHub 에서 다시 열린 alert(재발 · dismiss 취소)은 다음 upsert 로 다시 열림이 된다."""
    _seed(db, repo, [5])
    security_alert_log_repo.close_missing_alerts(db, repo_id=repo.id, alert_type="code_scanning", open_numbers=set())
    (log,) = _seed(db, repo, [5])
    assert log.github_state == security_alert_log_repo.OPEN


def test_list_pending_excludes_alerts_closed_on_github(db, repo):
    """🔴 GitHub 에서 닫힌 alert 은 «열린 alert» 목록에서 빠진다 — 이전엔 영원히 남았다."""
    kept, _gone = _seed(db, repo, [1, 2])
    security_alert_log_repo.close_missing_alerts(db, repo_id=repo.id, alert_type="code_scanning", open_numbers={1})
    assert [row.id for row in security_alert_log_repo.list_pending(db)] == [kept.id]


def test_count_alerts_reports_total_open_and_closed(db, repo):
    """카운트 dict — 누적 · 열림(pending) · 닫힘."""
    _seed(db, repo, [1, 2, 3])
    security_alert_log_repo.close_missing_alerts(db, repo_id=repo.id, alert_type="code_scanning", open_numbers={3})
    assert security_alert_log_repo.count_alerts(db) == {"total": 3, "pending": 1, "closed": 2}
