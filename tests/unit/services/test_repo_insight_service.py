"""repo_insight_service 단위 테스트 — 5 집계 함수 + AI narrative.

In-memory SQLite + Base.metadata.create_all 자체 fixture 사용.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import src.models  # noqa: F401  side-effect: populate Base.metadata
from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(github_id=99, github_login="tester", email="t@x.com", display_name="T")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def repo(db, user):
    r = Repository(full_name="owner/myrepo", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _add_analysis(
    db: Session,
    repo_id: int,
    *,
    offset_hours: int = 0,
    result: dict[str, Any] | None = None,
    score: int = 70,
) -> Analysis:
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="C",
        result=result or {},
        created_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ─── repo_kpi ────────────────────────────────────────────────────────────


class TestRepoKpi:
    def test_returns_required_keys(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        _add_analysis(db, repo.id, score=80)
        result = repo_kpi(db, repo.id)

        assert set(result.keys()) >= {
            "avg_score", "grade", "analysis_count",
            "top_recurring_issue", "top_recurring_count",
            "high_security_count", "score_delta",
        }

    def test_empty_repo_returns_none_avg(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        result = repo_kpi(db, repo.id)
        assert result["avg_score"] is None
        assert result["analysis_count"] == 0

    def test_days_filter_excludes_old_analysis(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        _add_analysis(db, repo.id, offset_hours=24 * 40, score=50)  # 40 days ago
        result = repo_kpi(db, repo.id, days=30)
        assert result["analysis_count"] == 0

    def test_counts_high_security_issues(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        _add_analysis(db, repo.id, result={
            "issues": [
                {"category": "security", "severity": "HIGH", "message": "sql inj"},
                {"category": "code_quality", "severity": "error", "message": "line too long"},
            ]
        })
        result = repo_kpi(db, repo.id)
        assert result["high_security_count"] == 1

    def test_identifies_top_recurring_issue(self, db, repo):
        from src.services.repo_insight_service import repo_kpi

        issue = {"category": "code_quality", "severity": "warning", "message": "line too long"}
        for _ in range(3):
            _add_analysis(db, repo.id, result={"issues": [issue]})
        result = repo_kpi(db, repo.id)
        assert result["top_recurring_issue"] == "line too long"
        assert result["top_recurring_count"] == 3


# ─── repo_recurring_issues ───────────────────────────────────────────────


class TestRepoRecurringIssues:
    def test_returns_sorted_by_count(self, db, repo):
        from src.services.repo_insight_service import repo_recurring_issues

        for _ in range(3):
            _add_analysis(db, repo.id, result={"issues": [
                {"message": "A", "category": "code_quality", "severity": "warning", "tool": "pylint", "language": "python"},
            ]})
        _add_analysis(db, repo.id, result={"issues": [
            {"message": "B", "category": "security", "severity": "error", "tool": "bandit", "language": "python"},
        ]})

        result = repo_recurring_issues(db, repo.id)
        assert result[0]["message"] == "A"
        assert result[0]["count"] == 3
        assert result[1]["message"] == "B"

    def test_empty_returns_empty_list(self, db, repo):
        from src.services.repo_insight_service import repo_recurring_issues
        assert repo_recurring_issues(db, repo.id) == []

    def test_result_dict_has_required_keys(self, db, repo):
        from src.services.repo_insight_service import repo_recurring_issues

        _add_analysis(db, repo.id, result={"issues": [
            {"message": "x", "category": "security", "severity": "error", "tool": "bandit", "language": "python"},
        ]})
        item = repo_recurring_issues(db, repo.id)[0]
        assert set(item.keys()) >= {"message", "count", "category", "severity", "tool", "language"}


# ─── repo_problem_files ──────────────────────────────────────────────────


class TestRepoProblemFiles:
    def test_returns_sorted_by_count(self, db, repo):
        from src.services.repo_insight_service import repo_problem_files

        for _ in range(4):
            _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "src/main.py", "text": "x"}]})
        _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "src/other.py", "text": "y"}]})

        result = repo_problem_files(db, repo.id)
        assert result[0]["file"] == "src/main.py"
        assert result[0]["count"] == 4
        assert result[0]["pct"] == 100

    def test_pct_calculated_relative_to_max(self, db, repo):
        from src.services.repo_insight_service import repo_problem_files

        for _ in range(4):
            _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "a.py", "text": "x"}]})
        for _ in range(2):
            _add_analysis(db, repo.id, result={"file_feedbacks": [{"file": "b.py", "text": "y"}]})

        result = repo_problem_files(db, repo.id)
        assert result[0]["pct"] == 100
        assert result[1]["pct"] == 50

    def test_empty_returns_empty_list(self, db, repo):
        from src.services.repo_insight_service import repo_problem_files
        assert repo_problem_files(db, repo.id) == []


# ─── repo_ai_suggestions ─────────────────────────────────────────────────


class TestRepoAiSuggestions:
    def test_groups_by_60char_prefix(self, db, repo):
        from src.services.repo_insight_service import repo_ai_suggestions

        suggestion = "A" * 70  # longer than 60 chars — two identical prefixes
        for _ in range(2):
            _add_analysis(db, repo.id, result={
                "ai_review_status": "success",
                "ai_suggestions": [suggestion],
            })
        result = repo_ai_suggestions(db, repo.id)
        assert len(result) == 1
        assert result[0]["count"] == 2

    def test_excludes_non_success_analyses(self, db, repo):
        from src.services.repo_insight_service import repo_ai_suggestions

        _add_analysis(db, repo.id, result={
            "ai_review_status": "error",
            "ai_suggestions": ["fix this"],
        })
        assert repo_ai_suggestions(db, repo.id) == []

    def test_empty_returns_empty_list(self, db, repo):
        from src.services.repo_insight_service import repo_ai_suggestions
        assert repo_ai_suggestions(db, repo.id) == []


# ─── repo_category_breakdown ─────────────────────────────────────────────


class TestRepoCategoryBreakdown:
    def test_returns_5_keys(self, db, repo):
        from src.services.repo_insight_service import repo_category_breakdown

        result = repo_category_breakdown(db, repo.id)
        assert set(result.keys()) == {
            "security_error", "security_warning",
            "code_quality_error", "code_quality_warning", "total",
        }

    def test_counts_by_category_and_severity(self, db, repo):
        from src.services.repo_insight_service import repo_category_breakdown

        _add_analysis(db, repo.id, result={"issues": [
            {"category": "security", "severity": "error"},    # 소문자 error
            {"category": "security", "severity": "HIGH"},     # 대문자 HIGH (bandit 저장 형식)
            {"category": "security", "severity": "warning"},
            {"category": "code_quality", "severity": "error"},
            {"category": "code_quality", "severity": "warning"},
        ]})
        bd = repo_category_breakdown(db, repo.id)
        assert bd["security_error"] == 2   # error + HIGH 양쪽 모두 집계
        assert bd["security_warning"] == 1
        assert bd["code_quality_error"] == 1
        assert bd["code_quality_warning"] == 1
        assert bd["total"] == 5

    def test_empty_all_zeros(self, db, repo):
        from src.services.repo_insight_service import repo_category_breakdown
        bd = repo_category_breakdown(db, repo.id)
        assert bd["total"] == 0


# ─── repo_insight_narrative ────────────────────────────────────────────────


class TestRepoInsightNarrative:
    """repo_insight_narrative async 함수 — 캐시/API/fallback 경로 검증."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_no_api_key_status(self, db, repo):
        """ANTHROPIC_API_KEY 미설정 → no_api_key."""
        from src.services.repo_insight_service import repo_insight_narrative
        with patch("src.services.repo_insight_service.settings") as s:
            s.anthropic_api_key = None
            result = await repo_insight_narrative(
                db, repo.id, kpi={"analysis_count": 5, "avg_score": 80, "grade": "B",
                                   "score_delta": 1, "high_security_count": 0,
                                   "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
            )
        assert result == {"text": "", "status": "no_api_key"}

    @pytest.mark.asyncio
    async def test_no_data_returns_no_data_status(self, db, repo):
        """analysis_count=0 → no_data (API 호출 X)."""
        from src.services.repo_insight_service import repo_insight_narrative
        with patch("src.services.repo_insight_service.settings") as s:
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            result = await repo_insight_narrative(
                db, repo.id, kpi={"analysis_count": 0}, recurring=[],
            )
        assert result == {"text": "", "status": "no_data"}

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api_call(self, db, repo, user):
        """user_id 제공 + 유효 캐시 → API 호출 없이 캐시 반환."""
        from src.repositories import insight_narrative_cache_repo
        from src.services.repo_insight_service import repo_insight_narrative

        cached = {"text": "cached narrative", "status": "success"}
        insight_narrative_cache_repo.upsert_repo(
            db, user_id=user.id, repo_id=repo.id, days=30, response=cached,
        )
        with patch("src.services.repo_insight_service.settings") as s:
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            result = await repo_insight_narrative(
                db, repo.id, user_id=user.id,
                kpi={"analysis_count": 5, "avg_score": 80, "grade": "B",
                     "score_delta": 1, "high_security_count": 0,
                     "top_recurring_issue": "x", "top_recurring_count": 1},
                recurring=[],
            )
        assert result == cached

    @pytest.mark.asyncio
    async def test_api_success_stores_in_cache(self, db, repo, user):
        """API 성공 + user_id 제공 → 결과 캐시 저장."""
        from src.repositories import insight_narrative_cache_repo
        from src.services.repo_insight_service import repo_insight_narrative

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"text": "great repo"}')]
        mock_msg.usage = MagicMock(input_tokens=10, output_tokens=20)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic", return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            result = await repo_insight_narrative(
                db, repo.id, user_id=user.id,
                kpi={"analysis_count": 3, "avg_score": 75, "grade": "C",
                     "score_delta": -2, "high_security_count": 1,
                     "top_recurring_issue": "sql injection", "top_recurring_count": 2},
                recurring=[{"message": "sql injection", "count": 2, "category": "security",
                            "severity": "error", "tool": "bandit", "language": "python"}],
            )
        assert result["status"] == "success"
        assert result["text"] == "great repo"
        cached = insight_narrative_cache_repo.get_fresh_repo(db, user_id=user.id, repo_id=repo.id, days=30)
        assert cached == result

    @pytest.mark.asyncio
    async def test_api_error_returns_api_error_status(self, db, repo):
        """API 예외 → api_error."""
        from src.services.repo_insight_service import repo_insight_narrative

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=RuntimeError("network down"))

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic", return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            result = await repo_insight_narrative(
                db, repo.id,
                kpi={"analysis_count": 2, "avg_score": 60, "grade": "D",
                     "score_delta": None, "high_security_count": 0,
                     "top_recurring_issue": None, "top_recurring_count": 0},
                recurring=[],
            )
        assert result == {"text": "", "status": "api_error"}

    @pytest.mark.asyncio
    async def test_refresh_invalidates_cache_and_calls_api(self, db, repo, user):
        """refresh=True → 기존 캐시 삭제 + API 재호출."""
        from src.repositories import insight_narrative_cache_repo
        from src.services.repo_insight_service import repo_insight_narrative

        # Seed stale cache
        insight_narrative_cache_repo.upsert_repo(
            db, user_id=user.id, repo_id=repo.id, days=30, response={"text": "old", "status": "success"}
        )

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"text": "refreshed narrative"}')]
        mock_msg.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic", return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            result = await repo_insight_narrative(
                db, repo.id, user_id=user.id, refresh=True,
                kpi={"analysis_count": 2, "avg_score": 70, "grade": "C",
                     "score_delta": 5, "high_security_count": 0,
                     "top_recurring_issue": None, "top_recurring_count": 0},
                recurring=[],
            )
        assert result["text"] == "refreshed narrative"
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_user_id_does_not_cache(self, db, repo):
        """user_id=None → 캐시 저장 X."""
        from src.models.insight_narrative_cache import InsightNarrativeCache
        from src.services.repo_insight_service import repo_insight_narrative

        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"text": "narrative"}')]
        mock_msg.usage = MagicMock(input_tokens=5, output_tokens=10)
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        with patch("src.services.repo_insight_service.settings") as s, \
             patch("src.services.repo_insight_service.anthropic.AsyncAnthropic", return_value=mock_client):
            s.anthropic_api_key = "sk-ant-test"
            s.claude_insight_model = "claude-haiku-4-5-20251001"
            result = await repo_insight_narrative(
                db, repo.id, user_id=None,
                kpi={"analysis_count": 1, "avg_score": 80, "grade": "B",
                     "score_delta": None, "high_security_count": 0,
                     "top_recurring_issue": None, "top_recurring_count": 0},
                recurring=[],
            )
        assert result["status"] == "success"
        rows = db.query(InsightNarrativeCache).filter_by(repo_id=repo.id).all()
        assert rows == []
