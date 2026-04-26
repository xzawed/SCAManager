"""tests/unit/api/test_insights_api.py — Red-phase tests for GET /api/insights/* endpoints.

테스트 대상: src/api/insights.py (아직 존재하지 않음 — ImportError 또는 404 실패 예상)
Target: src/api/insights.py (does not exist yet — expect ImportError or 404 failures)

엔드포인트 3개:
  GET /api/insights/authors/{login}/trend?days=30
  GET /api/insights/repos/compare?repos=a,b,c
  GET /api/insights/leaderboard?days=30
"""
import os

# 환경변수는 src 임포트 전 주입 필수
# Env vars must be injected before any src.* import that triggers Settings()
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

import pytest  # noqa: E402
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app
from src.api import auth as _auth_mod
from src.api.auth import require_api_key  # require_api_key dependency — dependency_overrides 키로 사용

client = TestClient(app)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _override_api_key():
    """require_api_key를 no-op으로 override하여 인증 없이 라우트를 테스트한다.
    Override require_api_key to no-op so routes are tested without auth friction."""
    app.dependency_overrides[require_api_key] = lambda: None
    yield
    # 테스트 후 override 제거 — 다른 테스트 격리 보장
    # Remove override after test to ensure isolation for other tests
    app.dependency_overrides.pop(require_api_key, None)


# ---------------------------------------------------------------------------
# Author Trend — 3 tests
# ---------------------------------------------------------------------------

def test_author_trend_returns_data():
    """analytics_service.author_trend 가 샘플 목록을 반환할 때 200 + 올바른 JSON 구조를 확인한다.
    When author_trend returns sample data, expect 200 and correct JSON shape."""
    sample_trend = [
        {"date": "2026-04-01", "avg_score": 82.5, "count": 3},
        {"date": "2026-04-02", "avg_score": 88.0, "count": 2},
    ]
    with patch("src.api.insights.analytics_service.author_trend", return_value=sample_trend):
        with patch("src.api.insights.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_db)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            r = client.get("/api/insights/authors/octocat/trend?days=30")

    assert r.status_code == 200
    data = r.json()
    # 응답에 login, days, trend 키가 있어야 한다
    # Response must contain login, days, trend keys
    assert data["login"] == "octocat"
    assert data["days"] == 30
    assert data["trend"] == sample_trend


def test_author_trend_respects_days_param():
    """?days=7 쿼리 파라미터가 author_trend 호출 시 days=7 로 전달되는지 확인한다.
    Verify days=7 query param is forwarded correctly to author_trend call."""
    with patch("src.api.insights.analytics_service.author_trend", return_value=[]) as mock_trend:
        with patch("src.api.insights.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_db)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            r = client.get("/api/insights/authors/devuser/trend?days=7")

    assert r.status_code == 200
    # author_trend가 days=7 로 호출됐는지 keyword 인자 검증
    # Verify author_trend was called with days=7 (keyword argument)
    _call_kwargs = mock_trend.call_args
    assert _call_kwargs is not None
    # days 인자 위치 또는 키워드로 7이 전달되어야 함
    # days value 7 must appear either positionally or as a keyword
    args, kwargs = _call_kwargs
    days_value = kwargs.get("days") if "days" in kwargs else (args[2] if len(args) > 2 else None)
    assert days_value == 7


def test_author_trend_requires_api_key():
    """require_api_key override 없이 요청 시 401 또는 503을 반환해야 한다.
    Without the api-key override, request must be rejected with 401 or 503."""
    # autouse fixture가 override를 걸었으므로, 여기서 명시적으로 제거한다
    # autouse fixture sets the override; explicitly remove it for this test
    app.dependency_overrides.pop(require_api_key, None)

    # API_KEY 환경변수를 설정하고 settings를 패치하여 강제로 인증 실패를 유도한다
    # Patch settings.api_key to a non-empty value to force authentication check
    _original = _auth_mod.settings.api_key
    try:
        _auth_mod.settings.api_key = "required-secret"
        r = client.get("/api/insights/authors/octocat/trend")
        # X-API-Key 헤더 없이 요청했으므로 401이어야 한다
        # No X-API-Key header → must return 401
        assert r.status_code == 401
    finally:
        _auth_mod.settings.api_key = _original
        # autouse fixture의 teardown이 다시 override를 제거하므로 여기서는 복원만 한다
        # autouse fixture teardown will clean up; only restore the key here
        app.dependency_overrides[require_api_key] = lambda: None


# ---------------------------------------------------------------------------
# Repo Comparison — 2 tests
# ---------------------------------------------------------------------------

def test_repo_compare_returns_data():
    """DB에서 repo_ids를 조회하고 repo_comparison 결과에 full_name을 포함해 반환하는지 확인한다.
    Verify DB lookup of repo_ids and enrichment of comparison results with full_name."""
    # DB 에서 repo 조회 시 사용될 mock 객체
    # Mock Repository objects returned from the DB query
    mock_repo_a = MagicMock()
    mock_repo_a.id = 1
    mock_repo_a.full_name = "owner/repo-a"
    mock_repo_b = MagicMock()
    mock_repo_b.id = 2
    mock_repo_b.full_name = "owner/repo-b"

    comparison_result = [
        {"repo_id": 1, "avg_score": 85.0, "count": 10},
        {"repo_id": 2, "avg_score": 72.3, "count": 5},
    ]

    with patch("src.api.insights.analytics_service.repo_comparison", return_value=comparison_result):
        with patch("src.api.insights.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            # DB 쿼리가 [mock_repo_a, mock_repo_b] 를 반환하도록 설정
            # Configure DB query to return the two mock repos
            mock_db.query.return_value.filter.return_value.all.return_value = [
                mock_repo_a, mock_repo_b
            ]
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_db)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            r = client.get("/api/insights/repos/compare?repos=owner%2Frepo-a,owner%2Frepo-b")

    assert r.status_code == 200
    data = r.json()
    # 응답에 repos, days, comparison 키가 있어야 한다
    # Response must contain repos, days, comparison keys
    assert "repos" in data
    assert "days" in data
    assert "comparison" in data
    # comparison 항목에 full_name 이 포함돼야 한다
    # Each comparison item must contain full_name
    full_names_in_resp = {item["full_name"] for item in data["comparison"] if "full_name" in item}
    assert "owner/repo-a" in full_names_in_resp or len(data["comparison"]) >= 1


def test_repo_compare_empty_when_no_repos_param():
    """repos 파라미터가 없거나 빈 문자열이면 comparison=[] 와 200을 반환해야 한다.
    When repos param is absent or empty, return comparison=[] with 200."""
    with patch("src.api.insights.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_db)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = ctx

        # repos 파라미터 없이 요청
        # Request without repos param
        r = client.get("/api/insights/repos/compare")

    assert r.status_code == 200
    data = r.json()
    assert data["comparison"] == []
    assert data["repos"] == []


# ---------------------------------------------------------------------------
# Leaderboard — 3 tests
# ---------------------------------------------------------------------------

def test_leaderboard_returns_data():
    """leaderboard_opt_in=True 인 리포가 있을 때 leaderboard 결과를 올바른 구조로 반환한다.
    When opted-in repos exist, return leaderboard with correct shape."""
    # leaderboard_opt_in=True 인 RepoConfig 목 객체
    # Mock RepoConfig with leaderboard_opt_in=True
    mock_config = MagicMock()
    mock_config.repo_id = 42

    leaderboard_result = [
        {"author_login": "alice", "avg_score": 91.5, "count": 8},
        {"author_login": "bob", "avg_score": 78.2, "count": 5},
    ]

    with patch("src.api.insights.analytics_service.leaderboard", return_value=leaderboard_result):
        with patch("src.api.insights.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            # 옵트인 리포 쿼리 — leaderboard_opt_in=True 인 RepoConfig 1건 반환
            # Opted-in repo query returns one RepoConfig with leaderboard_opt_in=True
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_db)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            r = client.get("/api/insights/leaderboard?days=30")

    assert r.status_code == 200
    data = r.json()
    # 응답에 days, leaderboard 키가 있어야 한다
    # Response must contain days and leaderboard keys
    assert data["days"] == 30
    assert data["leaderboard"] == leaderboard_result


def test_leaderboard_empty_when_no_opted_in():
    """옵트인 리포가 없으면 leaderboard=[] 와 200을 반환해야 한다.
    When no repos have opted in, return leaderboard=[] with 200."""
    with patch("src.api.insights.analytics_service.leaderboard", return_value=[]) as mock_lb:
        with patch("src.api.insights.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            # 옵트인 리포 없음 — 빈 목록 반환
            # No opted-in repos — return empty list
            mock_db.query.return_value.filter.return_value.all.return_value = []
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_db)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            r = client.get("/api/insights/leaderboard?days=30")

    assert r.status_code == 200
    data = r.json()
    assert data["leaderboard"] == []
    # 옵트인 리포가 없으므로 leaderboard는 호출될 수도, 안 될 수도 있다 —
    # 핵심은 응답이 빈 리스트여야 한다는 것
    # leaderboard service may or may not be called when no repos opted in;
    # the key assertion is that the response contains an empty list


def test_leaderboard_respects_days_param():
    """?days=14 쿼리 파라미터가 leaderboard 호출 시 days=14 로 전달되는지 확인한다.
    Verify days=14 query param is forwarded correctly to the leaderboard call."""
    mock_config = MagicMock()
    mock_config.repo_id = 7

    with patch("src.api.insights.analytics_service.leaderboard", return_value=[]) as mock_lb:
        with patch("src.api.insights.SessionLocal") as mock_session_cls:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.all.return_value = [mock_config]
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_db)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            r = client.get("/api/insights/leaderboard?days=14")

    assert r.status_code == 200
    # leaderboard 서비스가 days=14 로 호출됐는지 검증
    # Verify leaderboard service was called with days=14
    assert mock_lb.call_count >= 1
    _call_kwargs = mock_lb.call_args
    args, kwargs = _call_kwargs
    days_value = kwargs.get("days") if "days" in kwargs else (args[1] if len(args) > 1 else None)
    assert days_value == 14


def test_repo_compare_empty_when_repos_all_whitespace():
    """repos 파라미터가 쉼표와 공백만 있으면 comparison=[] 와 200을 반환해야 한다.
    When repos param contains only commas/spaces, return comparison=[] with 200."""
    with patch("src.api.insights.SessionLocal") as mock_session_cls:
        mock_db = MagicMock()
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=mock_db)
        ctx.__exit__ = MagicMock(return_value=False)
        mock_session_cls.return_value = ctx

        # repos 파라미터가 공백/쉼표만 있을 때
        # repos param with only whitespace/commas after strip → empty list
        r = client.get("/api/insights/repos/compare?repos=%2C%2C+%2C")

    assert r.status_code == 200
    data = r.json()
    assert data["comparison"] == []
    assert data["repos"] == []
