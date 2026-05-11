"""repo_insight_cards 단위 테스트 — 대시보드 리포별 인사이트 카드 섹션.

repo_insight_cards unit tests — dashboard per-repo insight card section.
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
