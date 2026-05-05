"""dashboard_service.dashboard_usage — Cycle 79 PR 3b 회귀 가드.

본인 사용량 (SaaS Phase 1 read-only) — user_id 직접 격리 검증.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.services.dashboard_service import dashboard_usage


@pytest.fixture
def db():
    """In-memory SQLite + 단위 격리."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def alice(db):
    u = User(
        github_login="alice", github_id=1,
        email="alice@example.com", display_name="Alice",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def bob(db):
    """RLS 격리 검증용 다른 사용자."""
    u = User(
        github_login="bob", github_id=2,
        email="bob@example.com", display_name="Bob",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _add_analysis(db, repo_id, sha, score, days_ago=0):
    """헬퍼: 과거 시점 Analysis 추가."""
    now = datetime.now(timezone.utc)
    a = Analysis(
        repo_id=repo_id, commit_sha=sha,
        score=score, grade="B",
        created_at=now - timedelta(days=days_ago),
    )
    db.add(a)
    db.commit()
    return a


# ─── Empty State ─────────────────────────────────────────────────────


def test_no_repos_returns_zero_counts(db, alice):
    """리포 0건 = 모든 카운트 0 + avg_score None."""
    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["repo_count"] == 0
    assert result["total_analyses"] == 0
    assert result["recent_analyses"] == 0
    assert result["avg_score"] is None
    assert result["last_analysis_at"] is None
    assert result["days"] == 30


# ─── 본인 데이터 ─────────────────────────────────────────────────────


def test_own_repo_count(db, alice):
    """본인 리포 카운트."""
    for full_name in ("alice/r1", "alice/r2", "alice/r3"):
        db.add(Repository(full_name=full_name, user_id=alice.id))
    db.commit()
    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["repo_count"] == 3


def test_total_analyses_includes_all_history(db, alice):
    """누적 분석 = days 무관 (전체 history)."""
    r = Repository(full_name="alice/r1", user_id=alice.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    # 최근 5건 + 과거 100일전 3건 = 총 8건
    for i in range(5):
        _add_analysis(db, r.id, f"recent-{i}".ljust(40, "x"), 80, days_ago=1)
    for i in range(3):
        _add_analysis(db, r.id, f"old-{i}".ljust(40, "x"), 70, days_ago=100)

    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["total_analyses"] == 8  # 누적 = 8 (days 무관)
    assert result["recent_analyses"] == 5  # 최근 30일 = 5


def test_avg_score_recent_only(db, alice):
    """평균 점수 = 최근 N일 만 (과거 분석 영향 X)."""
    r = Repository(full_name="alice/r1", user_id=alice.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    # 최근 80점, 과거 50점 — avg = 80 (과거 제외)
    _add_analysis(db, r.id, ("a" * 40), 80, days_ago=1)
    _add_analysis(db, r.id, ("b" * 40), 50, days_ago=100)

    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["avg_score"] == 80.0


def test_avg_score_none_when_no_recent(db, alice):
    """최근 N일 분석 0건 = avg_score None."""
    r = Repository(full_name="alice/r1", user_id=alice.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    _add_analysis(db, r.id, ("a" * 40), 80, days_ago=100)  # 과거 only
    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["avg_score"] is None


def test_last_analysis_at_includes_all_history(db, alice):
    """last_analysis_at = 전체 history 의 max (최근 N일 무관)."""
    r = Repository(full_name="alice/r1", user_id=alice.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    _add_analysis(db, r.id, ("a" * 40), 80, days_ago=100)
    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["last_analysis_at"] is not None


# ─── RLS 격리 (다른 사용자 데이터 노출 X) ────────────────────────


def test_isolates_other_users_repos(db, alice, bob):
    """alice 의 dashboard_usage 가 bob 의 리포 노출 X."""
    db.add(Repository(full_name="alice/r1", user_id=alice.id))
    db.add(Repository(full_name="bob/r1", user_id=bob.id))
    db.add(Repository(full_name="bob/r2", user_id=bob.id))
    db.commit()
    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["repo_count"] == 1  # alice 만 (bob 의 2건 노출 X)


def test_isolates_other_users_analyses(db, alice, bob):
    """alice 의 dashboard_usage 가 bob 의 분석 노출 X."""
    r_alice = Repository(full_name="alice/r1", user_id=alice.id)
    r_bob = Repository(full_name="bob/r1", user_id=bob.id)
    db.add_all([r_alice, r_bob])
    db.commit()
    db.refresh(r_alice)
    db.refresh(r_bob)
    _add_analysis(db, r_alice.id, ("a" * 40), 80, days_ago=1)
    _add_analysis(db, r_bob.id, ("b" * 40), 90, days_ago=1)
    _add_analysis(db, r_bob.id, ("c" * 40), 95, days_ago=1)

    result = dashboard_usage(db, user_id=alice.id, days=30)
    assert result["total_analyses"] == 1  # alice 만 (bob 의 2건 노출 X)
    assert result["avg_score"] == 80.0  # bob 의 평균 (92.5) 영향 X


# ─── days 파라미터 ────────────────────────────────────────────────


def test_days_parameter_changes_recent_window(db, alice):
    """days 파라미터 변경 = recent_analyses + avg_score 윈도우 변경."""
    r = Repository(full_name="alice/r1", user_id=alice.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    _add_analysis(db, r.id, ("a" * 40), 80, days_ago=5)
    _add_analysis(db, r.id, ("b" * 40), 70, days_ago=50)

    result_7 = dashboard_usage(db, user_id=alice.id, days=7)
    assert result_7["recent_analyses"] == 1
    assert result_7["days"] == 7

    result_90 = dashboard_usage(db, user_id=alice.id, days=90)
    assert result_90["recent_analyses"] == 2
    assert result_90["days"] == 90
