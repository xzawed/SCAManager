"""dashboard_service Phase 2 신규 함수 단위 테스트.

Phase 2 PR 1 (2026-05-02): MCP 운영 데이터 검증 결과 (success_rate 16.6% / unstable_ci 79%) 반영.

신규 함수 2종:
- auto_merge_kpi(db, days, *, now) -> dict
  · 단순 시도 success rate + retry-aware final success rate (distinct PR 기준)
  · 운영 신호: retry queue 활발한데 final success 가 낮은 사례 식별
- merge_failure_distribution(db, days, *, n=5, now) -> list[dict]
  · 실패 사유 Top N + 비율 (운영 데이터: unstable_ci 압도적 우선)
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_attempt import MergeAttempt
from src.models.repository import Repository
from src.models.user import User


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(github_id=1, github_login="tester", email="t@x.com", display_name="Tester")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def repo(db, user):
    r = Repository(full_name="owner/repo", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _make_analysis(db: Session, repo_id: int, score: int = 80, *, offset_hours: int = 0) -> Analysis:
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="B",
        created_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _make_attempt(
    db: Session,
    *,
    analysis_id: int,
    repo_name: str = "owner/repo",
    pr_number: int = 1,
    score: int = 85,
    threshold: int = 75,
    success: bool = True,
    failure_reason: str | None = None,
    offset_hours: int = 0,
) -> MergeAttempt:
    m = MergeAttempt(
        analysis_id=analysis_id,
        repo_name=repo_name,
        pr_number=pr_number,
        score=score,
        threshold=threshold,
        success=success,
        failure_reason=failure_reason,
        attempted_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


# ─── auto_merge_kpi ────────────────────────────────────────────────────────


class TestAutoMergeKpi:
    """auto_merge_kpi — 단순 + retry-aware 양쪽 success rate 반환."""

    def test_returns_required_keys(self, db, repo):
        from src.services.dashboard_service import auto_merge_kpi

        a = _make_analysis(db, repo.id)
        _make_attempt(db, analysis_id=a.id, success=True)

        result = auto_merge_kpi(db, days=7)
        for key in ("value", "total_attempts", "success_count", "failure_count",
                    "delta", "distinct_prs", "final_success_prs", "final_success_rate_pct"):
            assert key in result, f"key 누락: {key}"

    def test_simple_success_rate(self, db, repo):
        """단순 시도 기준 success rate (16.6% 운영 데이터 패턴)."""
        from src.services.dashboard_service import auto_merge_kpi

        # 1 PR 에 대해 6 attempts: 1 success, 5 failure (운영 unstable_ci 패턴)
        a = _make_analysis(db, repo.id)
        _make_attempt(db, analysis_id=a.id, pr_number=10, success=True)
        for _ in range(5):
            _make_attempt(db, analysis_id=a.id, pr_number=10, success=False, failure_reason="unstable_ci")

        result = auto_merge_kpi(db, days=7)
        assert result["total_attempts"] == 6
        assert result["success_count"] == 1
        assert result["failure_count"] == 5
        # 단순 시도 기준 16.7%
        assert result["value"] == pytest.approx(16.7, abs=0.5)

    def test_final_success_rate_distinct_pr(self, db, repo):
        """retry-aware: 같은 PR 의 attempts 중 1건이라도 success → 최종 성공.

        운영 신호: 단순 success rate 16.6% 는 retry queue 다회 시도로 왜곡.
        distinct PR 기준 final_success_rate 가 더 의미 있음.
        """
        from src.services.dashboard_service import auto_merge_kpi

        # PR 100: 5 attempts, 1 success (재시도 후 결국 성공)
        a1 = _make_analysis(db, repo.id)
        _make_attempt(db, analysis_id=a1.id, pr_number=100, success=False, failure_reason="unstable_ci")
        _make_attempt(db, analysis_id=a1.id, pr_number=100, success=False, failure_reason="unstable_ci")
        _make_attempt(db, analysis_id=a1.id, pr_number=100, success=True)

        # PR 101: 3 attempts, 모두 실패
        a2 = _make_analysis(db, repo.id)
        for _ in range(3):
            _make_attempt(db, analysis_id=a2.id, pr_number=101, success=False, failure_reason="dirty_conflict")

        result = auto_merge_kpi(db, days=7)
        # distinct PR 2 (100, 101)
        assert result["distinct_prs"] == 2
        # PR 100 만 결국 성공 → 1
        assert result["final_success_prs"] == 1
        # 50% (1/2)
        assert result["final_success_rate_pct"] == pytest.approx(50.0, abs=0.5)

    def test_excludes_records_outside_days(self, db, repo):
        from src.services.dashboard_service import auto_merge_kpi

        a = _make_analysis(db, repo.id)
        _make_attempt(db, analysis_id=a.id, success=True, offset_hours=1)  # 윈도우 내
        _make_attempt(db, analysis_id=a.id, success=False, failure_reason="unstable_ci",
                      offset_hours=24 * 30)  # 윈도우 밖

        result = auto_merge_kpi(db, days=7)
        assert result["total_attempts"] == 1
        assert result["success_count"] == 1

    def test_delta_compares_previous_window(self, db, repo):
        from src.services.dashboard_service import auto_merge_kpi

        a = _make_analysis(db, repo.id)
        # 현재 윈도우 (0~7일): 2 success / 0 fail = 100%
        _make_attempt(db, analysis_id=a.id, pr_number=1, success=True, offset_hours=1)
        _make_attempt(db, analysis_id=a.id, pr_number=2, success=True, offset_hours=2)
        # 직전 윈도우 (7~14일): 1 success / 1 fail = 50%
        _make_attempt(db, analysis_id=a.id, pr_number=3, success=True, offset_hours=24 * 8)
        _make_attempt(db, analysis_id=a.id, pr_number=4, success=False,
                      failure_reason="unstable_ci", offset_hours=24 * 9)

        result = auto_merge_kpi(db, days=7)
        # delta = 100 - 50 = +50 (양수 = 개선)
        assert result["delta"] == pytest.approx(50.0, abs=1.0)

    def test_empty_db_returns_safe_defaults(self, db):
        from src.services.dashboard_service import auto_merge_kpi

        result = auto_merge_kpi(db, days=7)
        assert result["total_attempts"] == 0
        assert result["value"] is None
        assert result["distinct_prs"] == 0
        assert result["final_success_prs"] == 0
        assert result["final_success_rate_pct"] is None


# ─── merge_failure_distribution ─────────────────────────────────────────────


class TestMergeFailureDistribution:
    """merge_failure_distribution — 실패 사유 Top N + 비율 (운영 신호)."""

    def test_returns_top_n_sorted_by_count(self, db, repo):
        from src.services.dashboard_service import merge_failure_distribution

        a = _make_analysis(db, repo.id)
        # unstable_ci 5건, dirty_conflict 2건, permission_denied 1건
        for _ in range(5):
            _make_attempt(db, analysis_id=a.id, success=False, failure_reason="unstable_ci")
        for _ in range(2):
            _make_attempt(db, analysis_id=a.id, success=False, failure_reason="dirty_conflict")
        _make_attempt(db, analysis_id=a.id, success=False, failure_reason="permission_denied")

        result = merge_failure_distribution(db, days=7, n=5)

        assert len(result) == 3
        assert result[0]["reason"] == "unstable_ci"
        assert result[0]["count"] == 5
        # share_pct 검증 (5/8 = 62.5%)
        assert result[0]["share_pct"] == pytest.approx(62.5, abs=0.5)
        assert result[1]["reason"] == "dirty_conflict"
        assert result[2]["reason"] == "permission_denied"

    def test_excludes_success_attempts(self, db, repo):
        """success=True 는 제외 (실패 사유 분포만)."""
        from src.services.dashboard_service import merge_failure_distribution

        a = _make_analysis(db, repo.id)
        _make_attempt(db, analysis_id=a.id, success=True)
        _make_attempt(db, analysis_id=a.id, success=False, failure_reason="unstable_ci")

        result = merge_failure_distribution(db, days=7, n=5)
        assert len(result) == 1
        assert result[0]["reason"] == "unstable_ci"

    def test_n_limits_results(self, db, repo):
        from src.services.dashboard_service import merge_failure_distribution

        a = _make_analysis(db, repo.id)
        for reason in ("a", "b", "c", "d", "e", "f"):
            _make_attempt(db, analysis_id=a.id, success=False, failure_reason=reason)

        result = merge_failure_distribution(db, days=7, n=3)
        assert len(result) == 3

    def test_excludes_records_outside_days(self, db, repo):
        from src.services.dashboard_service import merge_failure_distribution

        a = _make_analysis(db, repo.id)
        _make_attempt(db, analysis_id=a.id, success=False, failure_reason="recent",
                      offset_hours=1)
        _make_attempt(db, analysis_id=a.id, success=False, failure_reason="old",
                      offset_hours=24 * 30)

        result = merge_failure_distribution(db, days=7, n=5)
        reasons = [r["reason"] for r in result]
        assert "recent" in reasons
        assert "old" not in reasons

    def test_empty_db_returns_empty(self, db):
        from src.services.dashboard_service import merge_failure_distribution

        assert merge_failure_distribution(db, days=7, n=5) == []
