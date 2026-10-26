"""repo_insight_cards 단위 테스트 — 대시보드 리포별 인사이트 카드 섹션.

repo_insight_cards unit tests — dashboard per-repo insight card section.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from src.database import Base
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.scorer.reliability import score_is_unreliable

NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
_NOW_NAIVE = NOW.replace(tzinfo=None)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def user(db):
    u = User(github_id=77, github_login="owner", email="o@x.com", display_name="O")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_repo(db, name, user_id):
    r = Repository(full_name=name, user_id=user_id)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def _make_analysis(db, repo_id, score, offset_hours=0, result=None):
    a = Analysis(
        repo_id=repo_id,
        commit_sha=f"sha-{uuid.uuid4().hex}",
        score=score,
        grade="B",
        result=result or {},
        created_at=datetime.now(timezone.utc) - timedelta(hours=offset_hours),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _add(db, repo_id, score, at, result=None):
    """`at`(naive UTC) 에 분석 1건 — 쓰기 경로처럼 `score_unreliable` 을 판정 함수로 채운다.
    One analysis at `at`; score_unreliable is filled from the predicate as the write paths do.
    """
    result = {} if result is None else result
    db.add(Analysis(
        repo_id=repo_id, commit_sha=f"sha-{uuid.uuid4().hex}", score=score, grade="B",
        result=result, score_unreliable=score_is_unreliable(result), created_at=at,
    ))


def _cards_by_repo(db, user_id, days):
    from src.services.dashboard_service import repo_insight_cards

    return {c["repo_id"]: c for c in repo_insight_cards(db, days=days, user_id=user_id, now=NOW)}


class TestCardsDoNotStarveEachOther:
    """리포마다 자기 최신 30건으로 카드를 만든다 — 바쁜 리포가 한도를 채워도 조용한 리포는 그대로다.
    Each repo's card uses its own newest 30 rows; a busy repo cannot crowd a quiet one out.
    """

    def test_quiet_repo_card_survives_busy_repo(self, db, user):
        busy = _make_repo(db, "owner/busy", user.id)
        quiet = _make_repo(db, "owner/quiet", user.id)
        for i in range(70):
            _add(db, busy.id, 90, _NOW_NAIVE - timedelta(hours=i + 1))
        for i in range(5):
            _add(db, quiet.id, 60, _NOW_NAIVE - timedelta(days=10, hours=i))
        db.commit()

        cards = _cards_by_repo(db, user.id, 30)
        assert quiet.id in cards
        assert (cards[quiet.id]["avg_score"], cards[quiet.id]["grade"]) == (60.0, "C")

    def test_quiet_repo_average_uses_its_own_rows(self, db, user):
        """조용한 리포의 최신 2건만 바쁜 리포 행 사이에 끼면 평균이 그 2건(100점)으로 바뀌던 것.
        Only the quiet repo's two newest rows used to survive, turning 64.0/C into 100.0/A.
        """
        busy = _make_repo(db, "owner/busy", user.id)
        quiet = _make_repo(db, "owner/quiet", user.id)
        _add(db, quiet.id, 100, _NOW_NAIVE - timedelta(minutes=1))
        _add(db, quiet.id, 100, _NOW_NAIVE - timedelta(minutes=2))
        for i in range(70):
            _add(db, busy.id, 90, _NOW_NAIVE - timedelta(hours=i + 1))
        for i in range(3):
            _add(db, quiet.id, 40, _NOW_NAIVE - timedelta(days=20, hours=i))
        db.commit()

        card = _cards_by_repo(db, user.id, 30)[quiet.id]
        assert (card["avg_score"], card["grade"]) == (64.0, "C")

    def test_quiet_repo_trend_uses_its_own_previous_rows(self, db, user):
        """직전 창도 같다 — 바쁜 리포가 직전 창을 채우면 조용한 리포의 비교값이 사라져 «flat» 이 됐다.
        The previous window too: the quiet repo lost its comparison and showed "flat".
        """
        busy = _make_repo(db, "owner/busy", user.id)
        quiet = _make_repo(db, "owner/quiet", user.id)
        _add(db, busy.id, 90, _NOW_NAIVE - timedelta(days=1))
        _add(db, quiet.id, 80, _NOW_NAIVE - timedelta(days=1, hours=1))
        for i in range(70):
            _add(db, busy.id, 90, _NOW_NAIVE - timedelta(days=7, minutes=i + 1))
        _add(db, quiet.id, 50, _NOW_NAIVE - timedelta(days=13))
        db.commit()

        assert _cards_by_repo(db, user.id, 7)[quiet.id]["score_trend"] == "up"

    def test_every_card_matches_its_repo_kpi(self, db, user):
        """카드 = 그 리포 인사이트 페이지의 KPI(같은 기간 · 같은 행). r1 은 최신 30건만 95점이라
        리포당 30건 상한을 없애면 평균이 63.5 로 바뀌어 여기서 걸린다.
        Each card equals that repo's insights-page KPI; dropping the per-repo cap would turn r1's
        95.0 into 63.5 and fail here.
        """
        from src.services.dashboard_service import _score_trend
        from src.services.repo_insight_service import repo_kpi

        r1 = _make_repo(db, "owner/r1", user.id)
        r2 = _make_repo(db, "owner/r2", user.id)
        r3 = _make_repo(db, "owner/r3", user.id)
        for i in range(100):
            _add(db, r1.id, 95 if i < 30 else 50, _NOW_NAIVE - timedelta(minutes=i + 1))
        for i in range(12):
            _add(db, r2.id, 70 + i, _NOW_NAIVE - timedelta(days=5, hours=i))
        for i in range(2):
            _add(db, r2.id, 10, _NOW_NAIVE - timedelta(days=6, hours=i), result={"source": "cli"})
        for i, score in enumerate((55, 65, 75)):
            _add(db, r3.id, score, _NOW_NAIVE - timedelta(days=20, hours=i))
        for i in range(100):
            _add(db, r1.id, 60, _NOW_NAIVE - timedelta(days=30, minutes=i + 1))
        for i in range(4):
            _add(db, r2.id, 60, _NOW_NAIVE - timedelta(days=50, hours=i))
        for i in range(2):
            _add(db, r3.id, 90, _NOW_NAIVE - timedelta(days=55, hours=i))
        db.commit()

        cards = _cards_by_repo(db, user.id, 30)
        assert set(cards) == {r1.id, r2.id, r3.id}
        for repo_id, card in cards.items():
            k = repo_kpi(db, repo_id, 30, now=NOW)
            assert (card["avg_score"], card["grade"], card["score_trend"]) == (
                k["avg_score"], k["grade"], _score_trend(k["score_delta"])), repo_id
        # 기대값을 손으로도 고정한다 — 두 쪽이 함께 틀리면 위 비교는 초록이다
        # Pin the values by hand too: the comparison above stays green if both sides go wrong together
        assert [(cards[r]["avg_score"], cards[r]["score_trend"]) for r in (r1.id, r2.id, r3.id)] == [
            (95.0, "up"), (75.5, "up"), (65.0, "down")]

    def test_query_count_does_not_grow_with_repos(self, db, user):
        """쿼리 수가 리포 수와 상관없다 — #408 의 N+1 개선을 지킨다(리포마다 따로 묻지 않는다).
        The query count does not depend on the repo count: keeps the #408 N+1 fix.
        """
        other = User(github_id=78, github_login="other", email="p@x.com", display_name="P")
        db.add(other)
        db.commit()
        owners = {user.id: 6, other.id: 2}
        for uid, n in owners.items():
            for k in range(n):
                r = _make_repo(db, f"o{uid}/r{k}", uid)
                _add(db, r.id, 80, _NOW_NAIVE - timedelta(days=1, hours=k))
                _add(db, r.id, 70, _NOW_NAIVE - timedelta(days=40, hours=k))
        db.commit()

        engine = db.get_bind()
        counts = {}
        for uid in owners:
            statements = []

            def _record(_conn, _cursor, statement, *_args, sink=statements):
                sink.append(statement)

            event.listen(engine, "before_cursor_execute", _record)
            try:
                cards = _cards_by_repo(db, uid, 30)
            finally:
                event.remove(engine, "before_cursor_execute", _record)
            assert len(cards) == owners[uid]
            counts[uid] = len(statements)
        assert counts[user.id] == counts[other.id], counts


class TestRepoInsightCards:
    def test_returns_list_of_cards(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/api", user.id)
        _make_analysis(db, r.id, 80)

        result = repo_insight_cards(db, days=30, user_id=user.id)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_card_has_required_keys(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/web", user.id)
        _make_analysis(db, r.id, 75)

        card = repo_insight_cards(db, days=30, user_id=user.id)[0]
        assert set(card.keys()) >= {
            "repo_id", "full_name", "avg_score", "grade",
            "recurring_issue_count", "score_trend", "insights_url",
        }

    def test_insights_url_format(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/my-repo", user.id)
        _make_analysis(db, r.id, 80)

        card = repo_insight_cards(db, days=30, user_id=user.id)[0]
        assert card["insights_url"] == "/repos/owner/my-repo/insights"

    def test_empty_repos_returns_empty_list(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        result = repo_insight_cards(db, days=30, user_id=user.id)
        assert result == []

    def test_score_trend_up_when_improved(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/cli", user.id)
        # Previous window: score 50 (35 days ago), current window: score 80 (5 hours ago)
        _make_analysis(db, r.id, 50, offset_hours=24 * 35)
        _make_analysis(db, r.id, 80, offset_hours=5)

        card = repo_insight_cards(db, days=30, user_id=user.id)[0]
        assert card["score_trend"] == "up"

    def test_max_10_repos(self, db, user):
        from src.services.dashboard_service import repo_insight_cards

        for i in range(12):
            r = _make_repo(db, f"owner/repo-{i}", user.id)
            _make_analysis(db, r.id, 70)

        result = repo_insight_cards(db, days=30, user_id=user.id)
        assert len(result) <= 10

    def test_recurring_issue_count_requires_two_or_more_occurrences(self, db, user):
        """recurring_issue_count는 count >= 2인 이슈만 카운트한다.

        recurring_issue_count only counts issues that appear >= 2 times.
        """
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/test-recur", user.id)
        # "issue-once" 1회 (recurring 아님), "issue-twice" 2회 (recurring)
        # "issue-once" appears once (not recurring), "issue-twice" appears twice (recurring)
        _make_analysis(db, r.id, 80, offset_hours=1, result={
            "issues": [
                {"message": "issue-once", "category": "code_quality", "tool": "pylint"},
                {"message": "issue-twice", "category": "code_quality", "tool": "pylint"},
            ]
        })
        _make_analysis(db, r.id, 75, offset_hours=2, result={
            "issues": [
                {"message": "issue-twice", "category": "code_quality", "tool": "pylint"},
            ]
        })

        cards = repo_insight_cards(db, days=30, user_id=user.id)
        assert len(cards) == 1
        # "issue-twice" 만 카운트 = 1 / Only "issue-twice" counts = 1
        assert cards[0]["recurring_issue_count"] == 1

    def test_recurring_issue_count_zero_when_all_single_occurrence(self, db, user):
        """모든 이슈가 1회씩만 등장하면 recurring_issue_count == 0.

        recurring_issue_count is 0 when all issues appear only once.
        """
        from src.services.dashboard_service import repo_insight_cards

        r = _make_repo(db, "owner/test-single", user.id)
        _make_analysis(db, r.id, 80, offset_hours=1, result={
            "issues": [
                {"message": "issue-a", "category": "code_quality", "tool": "pylint"},
                {"message": "issue-b", "category": "code_quality", "tool": "pylint"},
            ]
        })

        cards = repo_insight_cards(db, days=30, user_id=user.id)
        assert len(cards) == 1
        # 각 이슈가 1회만 등장 → recurring 없음 / Each issue appears once → no recurring
        assert cards[0]["recurring_issue_count"] == 0
