"""claude_api_cost_repo — record INSERT + user_cost_summary(owner 필터·모델별·delta)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database import Base
from src.models.claude_api_call import ClaudeApiCall  # noqa: F401
from src.models.repository import Repository  # noqa: F401
from src.models.user import User  # noqa: F401
from src.repositories import claude_api_cost_repo

NOW = datetime(2026, 7, 8, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed_user_repo(db):
    # User 모델에는 username 컬럼이 없음 — github_login/email/display_name(모두 nullable=False) 사용.
    # User model has no `username` column — use github_login/email/display_name (all non-nullable).
    u = User(id=7, github_id="700", github_login="u7", email="u7@x.com", display_name="U7")
    r = Repository(id=3, full_name="u7/repo", user_id=7)
    other = Repository(id=9, full_name="x/other", user_id=99)
    db.add_all([u, r, other]); db.commit()


def test_record_inserts_row(db):
    claude_api_cost_repo.record(
        db, model="claude-sonnet-4-6", status="success",
        input_tokens=100, output_tokens=50, cache_read_tokens=0, cache_creation_tokens=0,
        cost_usd=0.0012, duration_ms=800, repo_id=None, user_id=7,
    )
    assert db.query(ClaudeApiCall).count() == 1


def test_user_cost_summary_by_model_owner_filter_delta(db):
    _seed_user_repo(db)
    # user7: sonnet(repo_id=3, 소유) + haiku(user_id=7 직접) = 합산. 다른 user repo9 = 제외.
    claude_api_cost_repo.record(db, model="claude-sonnet-4-6", status="success",
        input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0,
        cost_usd=0.01, duration_ms=1, repo_id=3, user_id=None, now=NOW)
    claude_api_cost_repo.record(db, model="claude-haiku-4-5", status="success",
        input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0,
        cost_usd=0.002, duration_ms=1, repo_id=None, user_id=7, now=NOW)
    claude_api_cost_repo.record(db, model="claude-sonnet-4-6", status="success",
        input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0,
        cost_usd=0.05, duration_ms=1, repo_id=9, user_id=None, now=NOW)  # 다른 user — 제외
    s = claude_api_cost_repo.user_cost_summary(db, user_id=7, days=30, now=NOW)
    assert s["call_count"] == 2
    assert s["by_model"]["sonnet"] == pytest.approx(0.01)
    assert s["by_model"]["haiku"] == pytest.approx(0.002)
    assert s["total_usd"] == pytest.approx(0.012)
