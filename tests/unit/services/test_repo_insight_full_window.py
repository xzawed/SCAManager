"""repo_kpi · repo_score_trend 는 고른 기간 «전체» 를 쓴다 — 점수는 저장된 열로, 이슈는 기간 안 최근 30건으로.

repo_kpi / repo_score_trend cover the whole chosen window: scores from the stored columns, issue figures
from the latest 30 analyses in it.
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
from src.models.repository import Repository
from src.scorer.reliability import score_is_unreliable
from src.services.repo_insight_service import repo_kpi, repo_score_trend

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
_N = NOW.replace(tzinfo=None)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def repo_id(db):
    r = Repository(full_name="owner/full-window")
    db.add(r)
    db.commit()
    return r.id


def _add(db, repo_id, score, at, result=None):
    """`at`(naive UTC) 에 분석 1건 — 쓰기 경로처럼 `score_unreliable` 을 판정 함수로 채운다.
    One analysis at `at`; score_unreliable is filled from the predicate as the write paths do.
    """
    result = {} if result is None else result
    db.add(Analysis(
        repo_id=repo_id, commit_sha=f"sha-{uuid.uuid4().hex}", score=score, grade="B",
        result=result, score_unreliable=score_is_unreliable(result), created_at=at,
    ))


class TestKpiUsesWholeWindow:
    def test_average_and_count_cover_every_analysis_in_window(self, db, repo_id):
        """45건 — 최신 30건 90점 · 그 앞 15건 60점 → 80.0 / B · 분석 45건 (최신 30건만 보면 90.0 / A · 30건)."""
        for i in range(45):
            _add(db, repo_id, 90 if i < 30 else 60, _N - timedelta(hours=i + 1))
        db.commit()

        k = repo_kpi(db, repo_id, 30, now=NOW)
        assert (k["analysis_count"], k["avg_score"], k["grade"]) == (45, 80.0, "B")

    def test_delta_compares_whole_previous_window(self, db, repo_id):
        """직전 기간 40건 — 최신 30건 50점 · 그 앞 10건 90점 → 60.0, 변화 +20.0."""
        for i in range(45):
            _add(db, repo_id, 90 if i < 30 else 60, _N - timedelta(hours=i + 1))
        for i in range(40):
            _add(db, repo_id, 50 if i < 30 else 90, _N - timedelta(days=30, hours=i + 1))
        db.commit()

        assert repo_kpi(db, repo_id, 30, now=NOW)["score_delta"] == 20.0

    def test_unverified_rows_count_but_do_not_average(self, db, repo_id):
        """검증 40건(70점) + CLI 미검증 10건(10점) → 분석 50건 · 평균 70.0."""
        for i in range(40):
            _add(db, repo_id, 70, _N - timedelta(hours=i + 1))
        for i in range(10):
            _add(db, repo_id, 10, _N - timedelta(days=3, hours=i), result={"source": "cli"})
        db.commit()

        k = repo_kpi(db, repo_id, 30, now=NOW)
        assert (k["analysis_count"], k["avg_score"]) == (50, 70.0)

    def test_issue_figures_stay_on_latest_30(self, db, repo_id):
        """이슈 수치는 기간 안 최근 30건 그대로다 — 앞 15건의 "old" 이슈(45회)·보안 HIGH 는 들어오지 않는다.
        Issue figures keep the latest 30; the older rows' issues and HIGH findings stay out.
        """
        new = {"message": "new", "category": "code_quality", "severity": "warning"}
        old = {"message": "old", "category": "security", "severity": "HIGH"}
        for i in range(30):
            _add(db, repo_id, 80, _N - timedelta(hours=i + 1), result={"issues": [new]})
        for i in range(15):
            _add(db, repo_id, 80, _N - timedelta(days=5, hours=i), result={"issues": [old, old, old]})
        db.commit()

        k = repo_kpi(db, repo_id, 30, now=NOW)
        assert (k["top_recurring_issue"], k["top_recurring_count"], k["high_security_count"]) == ("new", 30, 0)
        assert k["analysis_count"] == 45

    def test_window_edges_and_null_result(self, db, repo_id):
        """경계는 지금과 같다 — `since` · `now` 포함, 그 밖과 결과가 SQL NULL 인 행은 뺀다.
        Edges are unchanged: since and now included; rows outside or with SQL NULL result excluded.
        """
        _add(db, repo_id, 70, _N - timedelta(days=30))
        _add(db, repo_id, 90, _N)
        _add(db, repo_id, 10, _N - timedelta(days=30, seconds=1))
        _add(db, repo_id, 10, _N + timedelta(seconds=1))
        db.add(Analysis(repo_id=repo_id, commit_sha="sha-null-result", score=10, grade="F",
                        score_unreliable=False, created_at=_N - timedelta(hours=1)))
        db.commit()

        k = repo_kpi(db, repo_id, 30, now=NOW)
        assert (k["analysis_count"], k["avg_score"]) == (2, 80.0)
        assert [p["count"] for p in repo_score_trend(db, repo_id, 30, now=NOW)] == [1, 1]


class TestTrendUsesWholeWindow:
    def test_every_day_in_window_has_a_point(self, db, repo_id):
        """10일 × 하루 4건 = 40건 → 점 10개 (최신 30건만 보면 8일)."""
        for d in range(10):
            for h in range(4):
                _add(db, repo_id, 60 + d, _N - timedelta(days=d, hours=h + 1))
        db.commit()

        trend = repo_score_trend(db, repo_id, 30, now=NOW)
        assert len(trend) == 10
        assert trend[0] == {"date": "2026-10-11", "avg_score": 69.0, "count": 4}
        assert trend[-1] == {"date": "2026-10-20", "avg_score": 60.0, "count": 4}

    def test_day_average_keeps_unverified_scores_and_skips_null(self, db, repo_id):
        """추세가 무엇을 평균하는지는 바꾸지 않는다 — 기록된 점수 전부(미검증 포함), 점수 NULL 만 뺀다.
        The trend still averages every recorded score (unverified included) and skips NULL scores.
        """
        _add(db, repo_id, 80, _N - timedelta(hours=1))
        _add(db, repo_id, 40, _N - timedelta(hours=2), result={"source": "cli"})
        _add(db, repo_id, None, _N - timedelta(hours=3), result={"ai_review_status": "api_error"})
        db.commit()

        assert repo_score_trend(db, repo_id, 30, now=NOW) == [
            {"date": "2026-10-20", "avg_score": 60.0, "count": 2}]


def test_kpi_keys_unchanged(db, repo_id):
    """API 상세(`/api/repos/{name}/report` 의 `kpi`)가 이 사전을 그대로 내보낸다 — 값만 바뀌고 키는 그대로다.
    The report API returns this dict as-is: values change, keys do not.
    """
    _add(db, repo_id, 80, _N - timedelta(hours=1))
    db.commit()
    assert set(repo_kpi(db, repo_id, 30, now=NOW)) == {
        "avg_score", "grade", "analysis_count", "top_recurring_issue", "top_recurring_count",
        "high_security_count", "score_delta"}


def test_narrative_prompt_states_the_issue_basis(db, repo_id):
    """서술 프롬프트도 이슈 수치가 최근 몇 건에서 왔는지 밝힌다 — «분석 45건» 옆의 이슈 횟수는 30건 안의 횟수다.
    The narrative prompt says the issue figures come from the latest 30 of the 45 analyses.
    """
    from src.services.repo_insight_service import _prepare_repo_narrative

    kpi = {"avg_score": 80.0, "grade": "B", "score_delta": 1.0, "analysis_count": 45,
           "high_security_count": 0, "top_recurring_issue": "x", "top_recurring_count": 3}
    prompt = _prepare_repo_narrative(db, repo_id, 30, repo_full_name="o/r", kpi=kpi, recurring=[],
                                     now=NOW, refresh=False, user_id=None, language="en")
    assert "Analyses: 45\n" in prompt
    assert "latest 30 of these analyses" in prompt
