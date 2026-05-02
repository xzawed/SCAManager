"""dashboard_service 단위 테스트 — Phase 1 PR 4 (MVP-B 신규 함수).

신규 함수 3종 검증:
- dashboard_kpi(db, days, *, now) -> dict (KPI 4 카드 — 평균 점수 / 분석 건수 / 보안 이슈 / 활성 리포)
- dashboard_trend(db, days, *, now) -> list[dict] (날짜별 평균 추세)
- frequent_issues_v2(db, days, *, n, now) -> list[dict] (자주 발생 이슈 — Q7 신규 함수)

In-memory SQLite + Base.metadata.create_all 자체 fixture 사용.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션을 제공한다."""
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
def repos(db, user):
    """3개 리포 fixture — 활성 리포 카운트 검증용."""
    repo_objs = []
    for name in ("owner/api", "owner/web", "owner/cli"):
        r = Repository(full_name=name, user_id=user.id)
        db.add(r)
        repo_objs.append(r)
    db.commit()
    for r in repo_objs:
        db.refresh(r)
    return repo_objs


def _make_analysis(
    db: Session,
    repo_id: int,
    score: int | None,
    *,
    offset_hours: int = 0,
    result: dict[str, Any] | None = None,
) -> Analysis:
    """Analysis 레코드 헬퍼 — created_at, result 주입 가능."""
    created = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="B",
        result=result,
        created_at=created,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ─── dashboard_kpi ──────────────────────────────────────────────────────────


class TestDashboardKpi:
    """dashboard_kpi — KPI 4 카드 (평균 점수 / 분석 건수 / 보안 이슈 HIGH / 활성 리포) 집계."""

    def test_returns_4_kpi_keys(self, db, repos):
        from src.services.dashboard_service import dashboard_kpi

        _make_analysis(db, repos[0].id, 80, offset_hours=1)
        result = dashboard_kpi(db, days=7)

        # 4 KPI 키가 모두 존재 (avg_score, analysis_count, high_security_issues, active_repos)
        assert set(result.keys()) >= {
            "avg_score", "analysis_count", "high_security_issues", "active_repos",
        }

    def test_avg_score_computed_within_days(self, db, repos):
        """현재 days 윈도우 내 평균 점수 정확 산출."""
        from src.services.dashboard_service import dashboard_kpi

        now = datetime.now(timezone.utc)
        _make_analysis(db, repos[0].id, 80, offset_hours=1)  # 윈도우 내
        _make_analysis(db, repos[0].id, 90, offset_hours=2)  # 윈도우 내
        _make_analysis(db, repos[0].id, 60, offset_hours=24 * 30)  # 윈도우 밖

        result = dashboard_kpi(db, days=7, now=now)
        assert result["avg_score"]["value"] == pytest.approx(85.0, abs=0.1)
        assert result["avg_score"]["grade"] in ("A", "B", "C", "D", "F", "B+")

    def test_avg_score_delta_compares_previous_window(self, db, repos):
        """delta = 현재 days 평균 - 직전 동일 days 평균 (양수 = 개선)."""
        from src.services.dashboard_service import dashboard_kpi

        now = datetime.now(timezone.utc)
        # 현재 윈도우 (0~7일): 평균 85
        _make_analysis(db, repos[0].id, 80, offset_hours=1)
        _make_analysis(db, repos[0].id, 90, offset_hours=2)
        # 직전 윈도우 (7~14일): 평균 75
        _make_analysis(db, repos[0].id, 70, offset_hours=24 * 8)
        _make_analysis(db, repos[0].id, 80, offset_hours=24 * 9)

        result = dashboard_kpi(db, days=7, now=now)
        # delta = 85 - 75 = +10
        assert result["avg_score"]["delta"] == pytest.approx(10.0, abs=0.5)

    def test_analysis_count_within_days(self, db, repos):
        """현재 윈도우 내 분석 건수 카운트."""
        from src.services.dashboard_service import dashboard_kpi

        now = datetime.now(timezone.utc)
        for _ in range(5):
            _make_analysis(db, repos[0].id, 80, offset_hours=1)
        # 윈도우 밖 1건
        _make_analysis(db, repos[0].id, 70, offset_hours=24 * 30)

        result = dashboard_kpi(db, days=7, now=now)
        assert result["analysis_count"]["value"] == 5

    def test_high_security_issues_count(self, db, repos):
        """Analysis.result['issues'] 중 category=security AND severity=HIGH 카운트."""
        from src.services.dashboard_service import dashboard_kpi

        now = datetime.now(timezone.utc)
        result_data = {
            "issues": [
                {"category": "security", "severity": "HIGH", "tool": "bandit", "message": "B608"},
                {"category": "security", "severity": "HIGH", "tool": "bandit", "message": "B102"},
                {"category": "security", "severity": "LOW", "tool": "bandit", "message": "B404"},
                {"category": "code_quality", "severity": "warning", "tool": "pylint", "message": "C0103"},
            ]
        }
        _make_analysis(db, repos[0].id, 80, offset_hours=1, result=result_data)

        result = dashboard_kpi(db, days=7, now=now)
        # HIGH 보안만 카운트 = 2
        assert result["high_security_issues"]["value"] == 2

    def test_active_repos_within_days(self, db, repos):
        """활성 리포 = 윈도우 내 분석 발생한 distinct repo_id 수."""
        from src.services.dashboard_service import dashboard_kpi

        now = datetime.now(timezone.utc)
        _make_analysis(db, repos[0].id, 80, offset_hours=1)
        _make_analysis(db, repos[1].id, 70, offset_hours=2)
        # repos[2] 는 분석 0 → 비활성

        result = dashboard_kpi(db, days=7, now=now)
        assert result["active_repos"]["value"] == 2
        assert result["active_repos"]["total"] == 3  # 전체 리포 수

    def test_empty_db_returns_safe_defaults(self, db):
        """분석 0건일 때 KPI 는 None / 0 의 안전 default."""
        from src.services.dashboard_service import dashboard_kpi

        result = dashboard_kpi(db, days=7)
        assert result["avg_score"]["value"] is None
        assert result["analysis_count"]["value"] == 0
        assert result["high_security_issues"]["value"] == 0
        assert result["active_repos"]["value"] == 0


# ─── dashboard_trend ──────────────────────────────────────────────────────


class TestDashboardTrend:
    """dashboard_trend — 날짜별 평균 점수 추세 (라인 차트용)."""

    def test_returns_daily_avg_sorted_ascending(self, db, repos):
        """날짜별 평균 점수 + count 반환, 날짜 오름차순."""
        from src.services.dashboard_service import dashboard_trend

        now = datetime(2026, 4, 30, 12, 0, 0, tzinfo=timezone.utc)
        # 2026-04-25 (5일 전): 80, 90 → avg 85
        d1 = now - timedelta(days=5)
        _make_analysis(db, repos[0].id, 80, offset_hours=int((now - d1).total_seconds() / 3600))
        _make_analysis(db, repos[0].id, 90, offset_hours=int((now - d1).total_seconds() / 3600))
        # 2026-04-28 (2일 전): 70
        d2 = now - timedelta(days=2)
        _make_analysis(db, repos[0].id, 70, offset_hours=int((now - d2).total_seconds() / 3600))

        result = dashboard_trend(db, days=7, now=now)
        assert len(result) == 2
        # 오름차순 (이전 날짜가 첫번째)
        assert result[0]["date"] < result[1]["date"]
        for entry in result:
            assert "date" in entry
            assert "avg_score" in entry
            assert "count" in entry

    def test_excludes_records_outside_days(self, db, repos):
        """days 밖 레코드는 제외."""
        from src.services.dashboard_service import dashboard_trend

        now = datetime.now(timezone.utc)
        _make_analysis(db, repos[0].id, 85, offset_hours=24 * 3)  # 3일 전 — 포함
        _make_analysis(db, repos[0].id, 50, offset_hours=24 * 30)  # 30일 전 — 제외

        result = dashboard_trend(db, days=7, now=now)
        assert len(result) == 1
        assert result[0]["avg_score"] == pytest.approx(85.0, abs=0.1)

    def test_empty_db_returns_empty_list(self, db):
        """분석 0건일 때 빈 리스트."""
        from src.services.dashboard_service import dashboard_trend

        assert dashboard_trend(db, days=7) == []


# ─── frequent_issues_v2 (Q7 신규 함수) ─────────────────────────────────────


class TestFrequentIssuesV2:
    """frequent_issues_v2 — global 자주 발생 이슈 (category/language/tool 포함).

    폐기된 top_issues 와 차이:
    - repo_id 인자 제거 (global 집계)
    - category/language/tool 필드 반환 (sorting/grouping 용이)
    """

    def test_returns_sorted_by_frequency(self, db, repos):
        from src.services.dashboard_service import frequent_issues_v2

        now = datetime.now(timezone.utc)
        # "issue-A" 3회, "issue-B" 2회, "issue-C" 1회
        analyses_data = [
            {"issues": [{"message": "issue-A", "category": "code_quality", "language": "python", "tool": "pylint"},
                        {"message": "issue-B", "category": "security", "language": "python", "tool": "bandit"}]},
            {"issues": [{"message": "issue-A", "category": "code_quality", "language": "python", "tool": "pylint"},
                        {"message": "issue-C", "category": "code_quality", "language": "javascript", "tool": "eslint"}]},
            {"issues": [{"message": "issue-A", "category": "code_quality", "language": "python", "tool": "pylint"},
                        {"message": "issue-B", "category": "security", "language": "python", "tool": "bandit"}]},
        ]
        for data in analyses_data:
            _make_analysis(db, repos[0].id, 80, offset_hours=1, result=data)

        result = frequent_issues_v2(db, days=7, n=5, now=now)
        assert len(result) == 3
        # 빈도 내림차순
        assert result[0]["message"] == "issue-A"
        assert result[0]["count"] == 3
        assert result[1]["count"] == 2
        # category/language/tool 필드 보존
        assert result[0]["category"] == "code_quality"
        assert result[0]["language"] == "python"
        assert result[0]["tool"] == "pylint"

    def test_global_aggregation_across_repos(self, db, repos):
        """다른 리포의 이슈도 합산 (repo_id 인자 없음)."""
        from src.services.dashboard_service import frequent_issues_v2

        now = datetime.now(timezone.utc)
        common_issue = {"issues": [{"message": "X", "category": "code_quality", "language": "python", "tool": "pylint"}]}
        _make_analysis(db, repos[0].id, 80, offset_hours=1, result=common_issue)
        _make_analysis(db, repos[1].id, 80, offset_hours=2, result=common_issue)
        _make_analysis(db, repos[2].id, 80, offset_hours=3, result=common_issue)

        result = frequent_issues_v2(db, days=7, n=5, now=now)
        assert len(result) == 1
        assert result[0]["message"] == "X"
        assert result[0]["count"] == 3

    def test_limits_to_n(self, db, repos):
        """n 인자로 결과 개수 제한."""
        from src.services.dashboard_service import frequent_issues_v2

        now = datetime.now(timezone.utc)
        result_data = {"issues": [
            {"message": f"issue-{i}", "category": "code_quality", "language": "python", "tool": "pylint"}
            for i in range(10)
        ]}
        _make_analysis(db, repos[0].id, 80, offset_hours=1, result=result_data)

        result = frequent_issues_v2(db, days=7, n=3, now=now)
        assert len(result) <= 3

    def test_empty_db_returns_empty(self, db):
        from src.services.dashboard_service import frequent_issues_v2

        assert frequent_issues_v2(db, days=7) == []
