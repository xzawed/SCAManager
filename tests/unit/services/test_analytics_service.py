"""analytics_service 단위 테스트 — TDD Red 단계.
Unit tests for analytics_service — TDD Red phase.

In-memory SQLite + Base.metadata.create_all 자체 fixture 사용.
Uses in-memory SQLite with Base.metadata.create_all — no conftest dependency.
"""
# pylint: disable=redefined-outer-name
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.models.user import User


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite DB
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    """모든 ORM 테이블이 생성된 in-memory SQLite 세션을 제공한다.
    Provide an in-memory SQLite session with all ORM tables created.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def repo(db):
    """테스트용 Repository 레코드를 생성하고 반환한다.
    Create and return a test Repository record.
    """
    user = User(github_id=1, github_login="tester", email="t@x.com", display_name="Tester")
    db.add(user)
    db.commit()
    db.refresh(user)

    repository = Repository(full_name="owner/testrepo", user_id=user.id)
    db.add(repository)
    db.commit()
    db.refresh(repository)
    return repository


def _make_analysis(db: Session, repo_id: int, score: int | None, offset_hours: int = 0) -> Analysis:
    """테스트용 Analysis 레코드를 생성하는 헬퍼 함수.
    Helper to create a test Analysis record.

    offset_hours: 현재 시각으로부터 얼마나 과거 시점인지 (음수면 미래)
    offset_hours: how many hours in the past from now (negative = future)
    """
    created = datetime.now(timezone.utc) - timedelta(hours=offset_hours)
    analysis = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{score}-{offset_hours}-{id(object())}",
        score=score,
        grade="B",
        created_at=created,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


# ---------------------------------------------------------------------------
# Test: weekly_summary
# ---------------------------------------------------------------------------


class TestWeeklySummary:
    """weekly_summary — 7일 집계 함수 테스트."""

    def test_weekly_summary_returns_aggregated_data(self, db, repo):
        """7일 윈도우 내 분석 3개 → count/avg/min/max 올바르게 집계된다.
        3 analyses within the 7-day window → count/avg/min/max are correctly aggregated.
        """
        from src.services.analytics_service import weekly_summary

        # 고정된 now를 기준으로 week_start 설정
        # Set week_start relative to a fixed now
        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=6)

        _make_analysis(db, repo.id, score=80, offset_hours=10)
        _make_analysis(db, repo.id, score=70, offset_hours=20)
        _make_analysis(db, repo.id, score=90, offset_hours=30)

        result = weekly_summary(db, repo.id, week_start, now=now)

        assert result is not None
        assert result["count"] == 3
        assert result["min_score"] == 70
        assert result["max_score"] == 90
        assert result["avg_score"] == pytest.approx(80.0, abs=0.1)
        assert "week_start" in result

    def test_weekly_summary_returns_none_when_empty(self, db, repo):
        """분석 레코드가 없으면 None을 반환한다.
        Return None when no analyses exist in the window.
        """
        from src.services.analytics_service import weekly_summary

        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=6)

        result = weekly_summary(db, repo.id, week_start, now=now)

        assert result is None

    def test_weekly_summary_excludes_null_scores(self, db, repo):
        """score=None인 레코드는 집계에서 제외된다.
        Records with score=None are excluded from the aggregation.
        """
        from src.services.analytics_service import weekly_summary

        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=6)

        # score가 있는 분석 1개 + NULL 분석 2개
        # 1 analysis with score, 2 with NULL score
        _make_analysis(db, repo.id, score=85, offset_hours=5)
        _make_analysis(db, repo.id, score=None, offset_hours=10)
        _make_analysis(db, repo.id, score=None, offset_hours=15)

        result = weekly_summary(db, repo.id, week_start, now=now)

        assert result is not None
        # NULL 제외 후 count는 1이어야 한다
        # count should be 1 after excluding NULLs
        assert result["count"] == 1
        assert result["avg_score"] == pytest.approx(85.0, abs=0.1)

    def test_weekly_summary_excludes_records_outside_window(self, db, repo):
        """week_start 이전 레코드는 윈도우에서 제외된다.
        Records before week_start are excluded from the window.
        """
        from src.services.analytics_service import weekly_summary

        now = datetime.now(timezone.utc)
        week_start = now - timedelta(days=3)

        # 윈도우 내 분석 1개, 윈도우 밖(8일 전) 분석 1개
        # 1 analysis inside window, 1 outside (8 days ago)
        _make_analysis(db, repo.id, score=80, offset_hours=24)       # 1일 전 — 윈도우 내
        _make_analysis(db, repo.id, score=50, offset_hours=8 * 24)   # 8일 전 — 윈도우 밖

        result = weekly_summary(db, repo.id, week_start, now=now)

        assert result is not None
        assert result["count"] == 1
        assert result["avg_score"] == pytest.approx(80.0, abs=0.1)


# ---------------------------------------------------------------------------
# Test: moving_average
# ---------------------------------------------------------------------------


class TestMovingAverage:
    """moving_average — 이동 평균 계산 함수 테스트."""

    def test_moving_average_returns_none_below_min_samples(self, db, repo):
        """min_samples=5 미만(4개)이면 None을 반환한다.
        Return None when sample count is below min_samples=5 (4 samples).
        """
        from src.services.analytics_service import moving_average

        now = datetime.now(timezone.utc)

        # 4개 분석 — min_samples=5 미만
        # 4 analyses — below min_samples=5
        for i in range(4):
            _make_analysis(db, repo.id, score=75, offset_hours=i * 10)

        result = moving_average(db, repo.id, window_days=7, min_samples=5, now=now)

        assert result is None

    def test_moving_average_returns_average_above_min_samples(self, db, repo):
        """min_samples=5 이상(6개)이면 평균 float을 반환한다.
        Return a float average when sample count meets min_samples=5 (6 samples).
        """
        from src.services.analytics_service import moving_average

        now = datetime.now(timezone.utc)

        # 6개 분석 — 점수 60, 70, 80, 90, 75, 85
        # 6 analyses — scores 60, 70, 80, 90, 75, 85
        scores = [60, 70, 80, 90, 75, 85]
        for i, score in enumerate(scores):
            _make_analysis(db, repo.id, score=score, offset_hours=i * 5)

        result = moving_average(db, repo.id, window_days=7, min_samples=5, now=now)

        assert result is not None
        expected = round(sum(scores) / len(scores), 1)
        assert result == expected

    def test_moving_average_excludes_records_outside_window(self, db, repo):
        """window_days 바깥 레코드는 이동 평균에서 제외된다.
        Records outside the window_days range are excluded from the moving average.
        """
        from src.services.analytics_service import moving_average

        now = datetime.now(timezone.utc)

        # 윈도우(3일) 내 5개, 윈도우 밖(10일 전) 1개
        # 5 inside window (3 days), 1 outside (10 days ago)
        inside_scores = [80, 85, 75, 90, 70]
        for i, score in enumerate(inside_scores):
            _make_analysis(db, repo.id, score=score, offset_hours=i * 10)
        _make_analysis(db, repo.id, score=10, offset_hours=10 * 24)  # 10일 전

        result = moving_average(db, repo.id, window_days=3, min_samples=5, now=now)

        assert result is not None
        # 10점짜리가 포함되면 평균이 크게 낮아짐 — 포함되지 않아야 함
        # If 10 is included, the average drops significantly — it must not be included
        expected = round(sum(inside_scores) / len(inside_scores), 1)
        assert result == expected


# ---------------------------------------------------------------------------
# Test: top_issues
# ---------------------------------------------------------------------------


class TestTopIssues:
    """top_issues — 상위 이슈 집계 함수 테스트."""

    def test_top_issues_returns_sorted_by_frequency(self, db, repo):
        """이슈가 여러 분석에 분산되어 있어도 빈도 내림차순으로 정렬된다.
        Issues spread across analyses are returned sorted by frequency (descending).
        """
        from src.services.analytics_service import top_issues

        now = datetime.now(timezone.utc)

        # "issue-A"는 3회, "issue-B"는 2회, "issue-C"는 1회 등장
        # "issue-A" appears 3 times, "issue-B" 2 times, "issue-C" 1 time
        analysis_data = [
            {"issues": [{"message": "issue-A"}, {"message": "issue-B"}]},
            {"issues": [{"message": "issue-A"}, {"message": "issue-C"}]},
            {"issues": [{"message": "issue-A"}, {"message": "issue-B"}]},
        ]

        for i, result_data in enumerate(analysis_data):
            a = Analysis(
                repo_id=repo.id,
                commit_sha=f"sha-top-{i}",
                score=80,
                grade="B",
                result=result_data,
                created_at=datetime.now(timezone.utc) - timedelta(hours=i * 5),
            )
            db.add(a)
        db.commit()

        result = top_issues(db, repo.id, days=30, n=5, now=now)

        assert len(result) == 3
        # 첫 번째는 "issue-A" (3회)여야 한다
        # First item must be "issue-A" (3 occurrences)
        assert result[0]["message"] == "issue-A"
        assert result[0]["count"] == 3
        # 두 번째는 "issue-B" (2회)
        # Second must be "issue-B" (2 occurrences)
        assert result[1]["message"] == "issue-B"
        assert result[1]["count"] == 2
        # 세 번째는 "issue-C" (1회)
        # Third must be "issue-C" (1 occurrence)
        assert result[2]["message"] == "issue-C"
        assert result[2]["count"] == 1

    def test_top_issues_returns_empty_when_no_analyses(self, db, repo):
        """분석 레코드가 없으면 빈 리스트를 반환한다.
        Return an empty list when no analyses exist.
        """
        from src.services.analytics_service import top_issues

        result = top_issues(db, repo.id, days=30, n=5)

        assert result == []

    def test_top_issues_limits_to_n(self, db, repo):
        """n=2이면 최대 2개만 반환한다.
        Return at most n=2 items when more exist.
        """
        from src.services.analytics_service import top_issues

        now = datetime.now(timezone.utc)

        # 5가지 이슈를 각기 다른 빈도로 삽입
        # Insert 5 distinct issues with different frequencies
        result_data = {
            "issues": [
                {"message": "issue-1"},
                {"message": "issue-2"},
                {"message": "issue-3"},
                {"message": "issue-4"},
                {"message": "issue-5"},
            ]
        }
        a = Analysis(
            repo_id=repo.id,
            commit_sha="sha-limit",
            score=80,
            grade="B",
            result=result_data,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(a)
        db.commit()

        result = top_issues(db, repo.id, days=30, n=2, now=now)

        # n=2이므로 최대 2개
        # At most 2 items since n=2
        assert len(result) <= 2

    def test_top_issues_excludes_records_outside_days_window(self, db, repo):
        """days 바깥의 분석 레코드는 집계에서 제외된다.
        Analyses outside the days window are excluded from the aggregation.
        """
        from src.services.analytics_service import top_issues

        now = datetime.now(timezone.utc)

        # 10일 이내 레코드 — 포함 대상
        # Record within 10 days — should be included
        a_inside = Analysis(
            repo_id=repo.id,
            commit_sha="sha-inside",
            score=80,
            grade="B",
            result={"issues": [{"message": "recent-issue"}]},
            created_at=now - timedelta(days=5),
        )
        # 40일 전 레코드 — 제외 대상
        # Record 40 days ago — should be excluded
        a_outside = Analysis(
            repo_id=repo.id,
            commit_sha="sha-outside",
            score=80,
            grade="B",
            result={"issues": [{"message": "old-issue"}]},
            created_at=now - timedelta(days=40),
        )
        db.add(a_inside)
        db.add(a_outside)
        db.commit()

        result = top_issues(db, repo.id, days=30, n=5, now=now)

        messages = [r["message"] for r in result]
        assert "recent-issue" in messages
        # old-issue는 30일 윈도우 밖이므로 포함되지 않아야 한다
        # old-issue is outside the 30-day window — must not appear
        assert "old-issue" not in messages


# ---------------------------------------------------------------------------
# Test: resolve_chat_id
# ---------------------------------------------------------------------------


class TestResolveChatId:
    """resolve_chat_id — chat_id 우선순위 라우팅 테스트."""

    def _make_repo(self, telegram_chat_id: str | None = None) -> object:
        """테스트용 Repository duck-type 객체를 생성한다 (DB 불필요).
        Create a duck-type Repository object without needing a DB session.

        SQLAlchemy instrumented attribute는 _sa_instance_state 없이 __new__ 로 생성하면
        직접 설정이 불가하므로 SimpleNamespace로 duck-typing 처리한다.
        SQLAlchemy instrumented attributes cannot be set via __new__ without
        _sa_instance_state, so we use SimpleNamespace for duck-typing.
        """
        from types import SimpleNamespace
        return SimpleNamespace(telegram_chat_id=telegram_chat_id)

    def _make_config(self, notify_chat_id: str | None = None) -> object:
        """테스트용 RepoConfig duck-type 객체를 생성한다 (DB 불필요).
        Create a duck-type RepoConfig object without needing a DB session.
        """
        from types import SimpleNamespace
        return SimpleNamespace(notify_chat_id=notify_chat_id)

    def test_resolve_chat_id_priority_notify_first(self, monkeypatch):
        """RepoConfig.notify_chat_id가 있으면 최우선으로 반환한다.
        Return RepoConfig.notify_chat_id first when it is set.
        """
        from src.services import analytics_service
        monkeypatch.setattr(analytics_service.settings, "telegram_chat_id", "global_chat")

        repo = self._make_repo(telegram_chat_id="repo_chat")
        config = self._make_config(notify_chat_id="config_chat")

        result = analytics_service.resolve_chat_id(repo, config)

        # notify_chat_id가 최우선
        # notify_chat_id has highest priority
        assert result == "config_chat"

    def test_resolve_chat_id_priority_repo_before_global(self, monkeypatch):
        """notify_chat_id 없으면 Repository.telegram_chat_id를 반환한다.
        Return Repository.telegram_chat_id when notify_chat_id is absent.
        """
        from src.services import analytics_service
        monkeypatch.setattr(analytics_service.settings, "telegram_chat_id", "global_chat")

        repo = self._make_repo(telegram_chat_id="repo_chat")
        config = self._make_config(notify_chat_id=None)  # 없음 / absent

        result = analytics_service.resolve_chat_id(repo, config)

        # repo chat_id가 두 번째 우선순위
        # repo chat_id is second priority
        assert result == "repo_chat"

    def test_resolve_chat_id_priority_global_fallback(self, monkeypatch):
        """notify_chat_id, repo.telegram_chat_id 모두 없으면 전역 settings를 반환한다.
        Return global settings.telegram_chat_id when both repo fields are absent.
        """
        from src.services import analytics_service
        monkeypatch.setattr(analytics_service.settings, "telegram_chat_id", "global_chat")

        repo = self._make_repo(telegram_chat_id=None)
        config = self._make_config(notify_chat_id=None)

        result = analytics_service.resolve_chat_id(repo, config)

        assert result == "global_chat"

    def test_resolve_chat_id_returns_none_when_all_empty(self, monkeypatch):
        """모든 chat_id 소스가 비어있으면 None을 반환한다.
        Return None when all chat_id sources are empty or None.
        """
        from src.services import analytics_service
        monkeypatch.setattr(analytics_service.settings, "telegram_chat_id", "")

        repo = self._make_repo(telegram_chat_id=None)
        config = self._make_config(notify_chat_id=None)

        result = analytics_service.resolve_chat_id(repo, config)

        # 모든 소스가 없으면 None
        # None when all sources are absent
        assert result is None

    def test_resolve_chat_id_with_none_config(self, monkeypatch):
        """config=None이어도 repo 및 전역 fallback으로 정상 동작한다.
        Work correctly with config=None, falling through to repo and global.
        """
        from src.services import analytics_service
        monkeypatch.setattr(analytics_service.settings, "telegram_chat_id", "global_chat")

        repo = self._make_repo(telegram_chat_id=None)

        result = analytics_service.resolve_chat_id(repo, None)

        # config=None → 전역 fallback 반환
        # config=None → global fallback returned
        assert result == "global_chat"
