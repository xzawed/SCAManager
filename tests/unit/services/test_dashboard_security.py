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
    """빈 DB → 0 카운트 + 빈 recent_pending. AI 분류 · «처리됨» 은 쓰는 곳이 없어 내보내지 않는다(회고 원장 L05 P2-87)."""
    result = dashboard_service.dashboard_security(db)
    assert result["total_alerts"] == 0
    assert result["pending_count"] == 0
    assert result["closed_count"] == 0
    assert result["recent_pending"] == []
    assert not {"classification", "processed_count"} & set(result), "쓰는 곳이 없는 칸이 남았다"


def test_dashboard_security_with_pending(db, repo):
    """pending alert 가 있으면 recent_pending 에 normalize 된 dict 포함."""
    security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo.id, alert_type="code_scanning", alert_number=1,
        severity="note", rule_id="py/unused-import",
    )
    result = dashboard_service.dashboard_security(db)
    assert result["total_alerts"] == 1
    assert result["pending_count"] == 1
    assert len(result["recent_pending"]) == 1
    row = result["recent_pending"][0]
    assert row["alert_number"] == 1
    assert row["severity"] == "note"
    assert "ai_classification" not in row, "늘 «pending» 이던 AI 분류 꼬리가 남았다"


def test_dashboard_security_counts_alerts_closed_on_github(db, repo):
    """🔴 GitHub 에서 닫힌 alert 은 «열린 alert» 에서 빠지고 «GitHub 에서 닫힘» 으로 센다 (회고 원장 L05 P1-35)."""
    for number in (1, 2):
        security_alert_log_repo.upsert_alert_log(db, repo_id=repo.id, alert_type="code_scanning", alert_number=number)
    security_alert_log_repo.close_missing_alerts(db, repo_id=repo.id, alert_type="code_scanning", open_numbers={2})
    result = dashboard_service.dashboard_security(db)
    assert (result["total_alerts"], result["pending_count"], result["closed_count"]) == (2, 1, 1)
    assert [r["alert_number"] for r in result["recent_pending"]] == [2]


def test_dashboard_security_isolates_by_repo_owner(db):
    """🔴 U0 cross-tenant 격리: user_id 명시 시 본인 소유 repo 알림만 노출 (타 테넌트 차단).

    이전 결함: dashboard_security 가 user_id 를 무시하고 list_pending/count_alerts
    을 전체 조회 → 모든 로그인 사용자가 타 테넌트 보안 알림 노출 (1차 앱 필터 부재).
    """
    repo_a = Repository(full_name="alice/repo", user_id=1)
    repo_b = Repository(full_name="bob/repo", user_id=2)
    db.add_all([repo_a, repo_b])
    db.commit()
    db.refresh(repo_a)
    db.refresh(repo_b)
    security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo_a.id, alert_type="code_scanning", alert_number=1,
        severity="high", rule_id="alice-rule",
    )
    security_alert_log_repo.upsert_alert_log(
        db, repo_id=repo_b.id, alert_type="code_scanning", alert_number=2,
        severity="high", rule_id="bob-secret",
    )

    # user 1(alice) 관점 — 본인 repo 알림 1건만, bob 알림 미노출
    result = dashboard_service.dashboard_security(db, user_id=1)
    assert result["total_alerts"] == 1
    assert len(result["recent_pending"]) == 1
    assert result["recent_pending"][0]["rule_id"] == "alice-rule"
    rule_ids = {r["rule_id"] for r in result["recent_pending"]}
    assert "bob-secret" not in rule_ids  # 🔴 타 테넌트 시크릿 룰 미노출

    # admin(user_id 미전달) — 전체 노출 (기존 동작 보존)
    admin_view = dashboard_service.dashboard_security(db)
    assert admin_view["total_alerts"] == 2


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
