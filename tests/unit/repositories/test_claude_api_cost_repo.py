"""claude_api_cost_repo — record INSERT + user_cost_summary(owner 필터·모델별·delta)."""
from datetime import datetime, timedelta, timezone

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


def test_user_cost_summary_window_boundaries_match_dashboard_kpi_convention(db):
    """윈도우 경계 3종 — dashboard_kpi 컨벤션(하한 항상 포함) 회귀 가드.
    Three window-boundary cases — regression guard for the dashboard_kpi convention
    (lower bound always inclusive).

    cur_since = NOW-30d, prev_since = NOW-60d.
    - cur_since 정각 로우 → cur 에 포함 (seam inversion 방지 — prev 로 새지 않음).
    - prev_since 정각 로우 → prev 에 포함 (data loss 방지 — 양쪽 윈도우 모두에서 누락 금지).
    - NOW 정각 로우 → cur 에 포함 (원래 버그 수정 대상).
    - row at cur_since exactly -> counted in cur (no seam inversion into prev).
    - row at prev_since exactly -> counted in prev (no silent data loss from both windows).
    - row at NOW exactly -> counted in cur (the original bug this fix addresses).
    """
    _seed_user_repo(db)
    cur_since = NOW - timedelta(days=30)
    prev_since = NOW - timedelta(days=60)

    claude_api_cost_repo.record(db, model="claude-sonnet-4-6", status="success",
        input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0,
        cost_usd=0.01, duration_ms=1, repo_id=None, user_id=7, now=cur_since)  # cur_since 정각 — cur
    claude_api_cost_repo.record(db, model="claude-sonnet-4-6", status="success",
        input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0,
        cost_usd=0.02, duration_ms=1, repo_id=None, user_id=7, now=prev_since)  # prev_since 정각 — prev
    claude_api_cost_repo.record(db, model="claude-sonnet-4-6", status="success",
        input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0,
        cost_usd=0.04, duration_ms=1, repo_id=None, user_id=7, now=NOW)  # NOW 정각 — cur

    s = claude_api_cost_repo.user_cost_summary(db, user_id=7, days=30, now=NOW)
    # cur = cur_since 로우(0.01) + NOW 로우(0.04) = 0.05, call_count = 2
    # cur = cur_since row(0.01) + NOW row(0.04) = 0.05, call_count = 2
    assert s["call_count"] == 2
    assert s["total_usd"] == pytest.approx(0.05)
    # prev_since 로우(0.02) 가 prev 에 포함 → delta = cur(0.05) - prev(0.02) = 0.03
    # prev_since row(0.02) counted in prev -> delta = cur(0.05) - prev(0.02) = 0.03
    assert s["delta_usd"] == pytest.approx(0.03)
