"""analytics_service 팀 인사이트 함수 TDD Red 단계 테스트.
TDD Red-phase tests for team-insights functions in analytics_service.

대상 함수 (아직 미구현 — ImportError/AttributeError 발생):
Target functions (not yet implemented — will raise ImportError/AttributeError):
  - author_trend(db, login, days=30, *, now=None) -> list[dict]
  - repo_comparison(db, repo_ids, days=30, *, now=None) -> list[dict]
  - leaderboard(db, days=30, opted_in_repo_ids=None, *, now=None) -> list[dict]

In-memory SQLite + Base.metadata.create_all 자체 fixture 사용.
Uses in-memory SQLite with Base.metadata.create_all — no shared conftest dependency.
"""
# pylint: disable=redefined-outer-name
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User


# ---------------------------------------------------------------------------
# Fixtures — in-memory SQLite DB (per-file pattern, no shared conftest)
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
def user(db):
    """테스트용 User 레코드를 생성하고 반환한다.
    Create and return a test User record.
    """
    u = User(github_id=99, github_login="tester", email="t@x.com", display_name="Tester")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def repo(db, user):
    """테스트용 Repository 레코드를 생성하고 반환한다.
    Create and return a test Repository record.
    """
    r = Repository(full_name="owner/repo-a", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture()
def repo2(db, user):
    """두 번째 테스트용 Repository 레코드를 생성하고 반환한다.
    Create and return a second test Repository record.
    """
    r = Repository(full_name="owner/repo-b", user_id=user.id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _make_analysis(
    db: Session,
    repo_id: int,
    score: int | None,
    *,
    author_login: str | None = None,
    created_at: datetime | None = None,
    offset_hours: int = 0,
) -> Analysis:
    """테스트용 Analysis 레코드를 생성하는 헬퍼 함수.
    Helper to create a test Analysis record.

    created_at이 주어지면 그대로 사용하고, 없으면 offset_hours만큼 과거 시각을 계산한다.
    Use the provided created_at directly; otherwise compute past time via offset_hours.
    """
    ts = created_at or (datetime.now(timezone.utc) - timedelta(hours=offset_hours))
    analysis = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{repo_id}-{score}-{offset_hours}-{id(object())}",
        score=score,
        grade="B",
        author_login=author_login,
        created_at=ts,
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


# ---------------------------------------------------------------------------
# Test: author_trend — 폐기 (Phase 1 PR 2, 2026-05-02)
# 회귀 가드는 tests/unit/services/test_analytics_service_deprecations.py 참조.
# Removed in Phase 1 PR 2; regression guard moved to test_analytics_service_deprecations.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Test: repo_comparison
# ---------------------------------------------------------------------------


class TestRepoComparison:
    """repo_comparison — 리포 간 평균 점수 비교 함수 테스트.
    Tests for cross-repo average score comparison.
    """

    def test_repo_comparison_returns_per_repo_stats(self, db, repo, repo2):
        """2개 리포에 다른 평균 점수 — 두 항목 모두 avg_score 내림차순으로 반환된다.
        2 repos with different avg scores → both appear, sorted by avg_score descending.
        """
        from src.services.analytics_service import repo_comparison  # noqa: F401

        now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(days=5)

        # repo: 점수 80, 90 → 평균 85
        # repo: scores 80, 90 → avg 85
        _make_analysis(db, repo.id, 80, created_at=ts)
        _make_analysis(db, repo.id, 90, created_at=ts.replace(hour=11))

        # repo2: 점수 60, 70 → 평균 65
        # repo2: scores 60, 70 → avg 65
        _make_analysis(db, repo2.id, 60, created_at=ts)
        _make_analysis(db, repo2.id, 70, created_at=ts.replace(hour=11))

        result = repo_comparison(db, [repo.id, repo2.id], days=30, now=now)

        # 두 리포 모두 반환되어야 한다
        # Both repos must be returned
        assert len(result) == 2

        # 각 항목에 repo_id, avg_score, count 키가 존재해야 한다
        # Each entry must have repo_id, avg_score, count keys
        for entry in result:
            assert "repo_id" in entry
            assert "avg_score" in entry
            assert "count" in entry

        # avg_score 내림차순 정렬 검증 — repo(85) > repo2(65)
        # Verify descending avg_score order — repo(85) > repo2(65)
        assert result[0]["repo_id"] == repo.id
        assert result[0]["avg_score"] == pytest.approx(85.0, abs=0.1)
        assert result[0]["count"] == 2

        assert result[1]["repo_id"] == repo2.id
        assert result[1]["avg_score"] == pytest.approx(65.0, abs=0.1)
        assert result[1]["count"] == 2

    def test_repo_comparison_empty_when_no_repo_ids(self, db):
        """repo_ids가 빈 리스트이면 빈 리스트를 반환한다 (안전 가드).
        Return an empty list when repo_ids is an empty list (safety guard).
        """
        from src.services.analytics_service import repo_comparison  # noqa: F401

        now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        result = repo_comparison(db, [], days=30, now=now)

        # 빈 repo_ids → 빈 결과
        # Empty repo_ids → empty result
        assert result == []


# ---------------------------------------------------------------------------
# Test: leaderboard
# ---------------------------------------------------------------------------


class TestLeaderboard:
    """leaderboard — opted-in 리포 기준 작성자별 순위표 함수 테스트.
    Tests for per-author leaderboard filtered to opted-in repos.
    """

    def test_leaderboard_returns_sorted_by_score(self, db, repo):
        """3명 작성자의 분석이 있을 때 avg_score 내림차순으로 정렬된다.
        With analyses from 3 authors, entries are sorted by avg_score descending.
        """
        from src.services.analytics_service import leaderboard  # noqa: F401

        now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(days=5)

        # alice: 평균 90, bob: 평균 75, carol: 평균 60
        # alice: avg 90, bob: avg 75, carol: avg 60
        _make_analysis(db, repo.id, 90, author_login="alice", created_at=ts)
        _make_analysis(db, repo.id, 75, author_login="bob",
                       created_at=ts.replace(hour=11))
        _make_analysis(db, repo.id, 60, author_login="carol",
                       created_at=ts.replace(hour=12))

        result = leaderboard(db, days=30, opted_in_repo_ids=[repo.id], now=now)

        # 3명 모두 반환되어야 한다
        # All 3 authors must be returned
        assert len(result) == 3

        # 각 항목에 author_login, avg_score, count 키가 존재해야 한다
        # Each entry must have author_login, avg_score, count keys
        for entry in result:
            assert "author_login" in entry
            assert "avg_score" in entry
            assert "count" in entry

        # avg_score 내림차순 정렬 검증
        # Verify descending avg_score order
        assert result[0]["author_login"] == "alice"
        assert result[0]["avg_score"] == pytest.approx(90.0, abs=0.1)

        assert result[1]["author_login"] == "bob"
        assert result[1]["avg_score"] == pytest.approx(75.0, abs=0.1)

        assert result[2]["author_login"] == "carol"
        assert result[2]["avg_score"] == pytest.approx(60.0, abs=0.1)

    def test_leaderboard_empty_when_no_opted_in_repos(self, db, repo):
        """opted_in_repo_ids가 None 또는 빈 리스트이면 빈 리스트를 반환한다 (안전 가드).
        Return an empty list when opted_in_repo_ids is None or [] (safety guard).
        """
        from src.services.analytics_service import leaderboard  # noqa: F401

        now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(days=5)
        _make_analysis(db, repo.id, 85, author_login="alice", created_at=ts)

        # opted_in_repo_ids=None — 아무도 opt-in 하지 않음
        # opted_in_repo_ids=None — no one has opted in
        result_none = leaderboard(db, days=30, opted_in_repo_ids=None, now=now)
        assert result_none == []

        # opted_in_repo_ids=[] — 빈 opt-in 목록
        # opted_in_repo_ids=[] — empty opt-in list
        result_empty = leaderboard(db, days=30, opted_in_repo_ids=[], now=now)
        assert result_empty == []

    def test_leaderboard_filters_to_opted_in_repos(self, db, repo, repo2):
        """repo1만 opt-in 했을 때 repo2의 분석은 리더보드에 나타나지 않는다.
        When only repo1 is opted in, repo2's analyses must not appear in the leaderboard.
        """
        from src.services.analytics_service import leaderboard  # noqa: F401

        now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(days=5)

        # alice는 repo1에서 분석 (opt-in 대상) → 포함
        # alice has analyses in repo1 (opted in) → should appear
        _make_analysis(db, repo.id, 90, author_login="alice", created_at=ts)

        # bob은 repo2에서 분석 (opt-in 미대상) → 제외
        # bob has analyses in repo2 (not opted in) → should be excluded
        _make_analysis(db, repo2.id, 95, author_login="bob",
                       created_at=ts.replace(hour=11))

        # repo1만 opt-in — bob이 더 높은 점수지만 제외되어야 한다
        # Only repo1 is opted in — bob has higher score but must be excluded
        result = leaderboard(db, days=30, opted_in_repo_ids=[repo.id], now=now)

        author_logins = [entry["author_login"] for entry in result]

        # alice만 반환되어야 한다
        # Only alice must be returned
        assert "alice" in author_logins
        assert "bob" not in author_logins
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Test: repo_comparison — min_score / max_score 포함 (Phase A+B 추가)
# Test: repo_comparison — includes min_score / max_score (added in Phase A+B)
# ---------------------------------------------------------------------------


class TestRepoComparisonMinMax:
    """repo_comparison이 min_score와 max_score를 반환해야 한다.
    repo_comparison must include min_score and max_score in its output.
    """

    def test_repo_comparison_includes_min_max(self, db, repo):
        """점수가 다른 여러 분석이 있을 때 min/max가 정확하게 포함되어야 한다.
        With multiple analyses of different scores, min/max must be included accurately.
        """
        from src.services.analytics_service import repo_comparison  # noqa: F401

        now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        ts_base = now - timedelta(days=5)

        _make_analysis(db, repo.id, 60, created_at=ts_base)
        _make_analysis(db, repo.id, 80, created_at=ts_base.replace(hour=13))
        _make_analysis(db, repo.id, 90, created_at=ts_base.replace(hour=14))

        result = repo_comparison(db, [repo.id], days=30, now=now)

        assert len(result) == 1
        item = result[0]

        # avg_score 검증
        # Verify avg_score
        assert item["avg_score"] == round((60 + 80 + 90) / 3, 1)

        # min_score / max_score 키가 존재하고 정확해야 한다
        # min_score / max_score keys must exist and be accurate
        assert "min_score" in item, "min_score 키가 결과에 없음 / min_score key missing from result"
        assert "max_score" in item, "max_score 키가 결과에 없음 / max_score key missing from result"
        assert item["min_score"] == 60
        assert item["max_score"] == 90

    def test_repo_comparison_single_analysis_min_equals_max(self, db, repo):
        """분석이 1건이면 min_score == max_score == avg_score가 되어야 한다.
        With a single analysis, min_score == max_score == avg_score.
        """
        from src.services.analytics_service import repo_comparison  # noqa: F401

        now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
        ts = now - timedelta(days=3)

        _make_analysis(db, repo.id, 75, created_at=ts)

        result = repo_comparison(db, [repo.id], days=30, now=now)

        assert len(result) == 1
        item = result[0]
        assert item["min_score"] == 75
        assert item["max_score"] == 75
        assert item["avg_score"] == pytest.approx(75.0)
