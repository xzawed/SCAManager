# tests/unit/api/test_issue_registration_api.py
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.auth.session import CurrentUser
from src.api.issue_registration import _make_issue_key, RegisterRequest


def _mock_user():
    return CurrentUser(
        id=1, github_login="user", email="u@example.com",
        display_name="User", plaintext_token="ghp_test",
    )


@pytest.fixture
def client():
    return TestClient(app)


def _mock_analysis(repo_id=1):
    m = MagicMock()
    m.id = 10
    m.repo_id = repo_id
    return m


def _mock_repo(full_name="owner/repo", user_id=1):
    m = MagicMock()
    m.id = 1
    m.full_name = full_name
    m.user_id = user_id
    return m


# ── POST /api/issues/register ──

def test_register_returns_401_when_not_logged_in(client):
    resp = client.post("/api/issues/register", json={
        "analysis_id": 1, "issue_type": "ai_suggestion",
        "suggestion_text": "text", "title": "T", "body": "B", "labels": [],
    })
    assert resp.status_code == 401


def test_register_returns_201_on_success(client):
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(return_value={
                  "github_issue_number": 44,
                  "github_issue_url": "https://github.com/owner/repo/issues/44",
                  "state": "open",
              })),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "cache TTL", "title": "T", "body": "B", "labels": ["bug"],
        })
    assert resp.status_code == 201
    assert resp.json()["github_issue_number"] == 44


def test_register_returns_409_on_duplicate(client):
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(side_effect=ValueError("DUPLICATE:38"))),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "text", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 409
    assert "38" in resp.json()["detail"]


def test_register_returns_403_on_permission_error(client):
    import httpx
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(side_effect=httpx.HTTPStatusError(
                  "403", request=MagicMock(),
                  response=MagicMock(status_code=403)))),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "t", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 403


# ── GET /api/issues/status ──

def test_status_returns_401_when_not_logged_in(client):
    resp = client.get("/api/issues/status?analysis_id=1")
    assert resp.status_code == 401


def test_status_returns_registrations(client):
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.get_analysis_issue_status",
              new=AsyncMock(return_value=[
                  {"issue_key": "k1", "github_issue_number": 44,
                   "github_issue_state": "open",
                   "github_issue_url": "https://github.com/owner/repo/issues/44"},
              ])),
    ):
        resp = client.get("/api/issues/status?analysis_id=10")
    assert resp.status_code == 200
    assert len(resp.json()["registrations"]) == 1


# ── GET /api/issues/repo-summary ──

def test_repo_summary_returns_401_when_not_logged_in(client):
    resp = client.get("/api/issues/repo-summary?repo_id=1")
    assert resp.status_code == 401


def test_repo_summary_returns_registrations(client):
    mock_repo = _mock_repo()
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_repo_or_404", return_value=mock_repo),
        patch("src.api.issue_registration.get_repo_issue_summary",
              new=AsyncMock(return_value=[
                  {"issue_key": "k1", "issue_type": "static_issue",
                   "github_issue_number": 55, "github_issue_state": "open",
                   "github_issue_url": "https://github.com/owner/repo/issues/55",
                   "created_at": "2026-05-24T00:00:00"},
              ])),
    ):
        resp = client.get("/api/issues/repo-summary?repo_id=1")
    assert resp.status_code == 200
    assert len(resp.json()["registrations"]) == 1


# ── _make_issue_key — static path (lines 64-67) ──

def test_make_issue_key_static_path():
    # static_issue 경로 커버 — tool/category/message 사용
    # Covers static_issue path using tool/category/message
    req = RegisterRequest(
        analysis_id=1, issue_type="static_issue",
        tool="bandit", category="B101", message="SQL injection",
        title="T", body="B", labels=[],
    )
    key = _make_issue_key(req)
    assert len(key) == 64


def test_make_issue_key_static_fallback_to_title():
    # message=None이면 title 폴백
    # Falls back to title when message is None
    req = RegisterRequest(
        analysis_id=1, issue_type="static_issue",
        tool="", category="", message=None, title="fallback", body="B", labels=[],
    )
    key = _make_issue_key(req)
    assert len(key) == 64


# ── _get_analysis_and_repo — error paths (lines 44-54) ──

def _mock_session_ctx(db_mock):
    """SessionLocal context manager mock 헬퍼.
    Helper that wraps db_mock as a context manager for SessionLocal.
    """
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_register_404_when_analysis_not_found(client):
    # analysis 조회 결과 None → 404
    # analysis query returns None → 404
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = None
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal", return_value=_mock_session_ctx(db_mock)),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 999, "issue_type": "ai_suggestion",
            "suggestion_text": "x", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 404


def test_register_404_when_repo_not_found(client):
    # analysis 있음 / repo 없음 → 404
    # analysis found / repo not found → 404
    analysis = _mock_analysis()
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.side_effect = [analysis, None]
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal", return_value=_mock_session_ctx(db_mock)),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "x", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 404


def test_register_404_on_ownership_denied(client):
    # 다른 user_id를 가진 repo → 소유권 거부 → 404
    # Repo owned by different user → ownership denied → 404
    analysis = _mock_analysis()
    repo = _mock_repo(user_id=99)  # current_user.id=1 vs repo.user_id=99
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.side_effect = [analysis, repo]
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal", return_value=_mock_session_ctx(db_mock)),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "x", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 404


# ── register endpoint — 500 / 502 error paths (lines 105, 112) ──

def test_register_returns_500_on_unexpected_value_error(client):
    # DUPLICATE가 아닌 ValueError → 500
    # Non-DUPLICATE ValueError → 500
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(side_effect=ValueError("unexpected internal error"))),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "x", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 500


def test_register_returns_502_on_github_5xx(client):
    # 403 이외의 GitHub API 오류 → 502
    # Non-403 GitHub API error → 502
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration._get_analysis_and_repo",
              return_value=(_mock_analysis(), _mock_repo())),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(side_effect=httpx.HTTPStatusError(
                  "500", request=MagicMock(),
                  response=MagicMock(status_code=500)))),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "x", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 502


# ── _get_repo_or_404 — error paths (lines 142-149) ──

def test_repo_summary_404_when_repo_not_found(client):
    # repo 없음 → 404
    # repo not found → 404
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = None
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal", return_value=_mock_session_ctx(db_mock)),
    ):
        resp = client.get("/api/issues/repo-summary?repo_id=999")
    assert resp.status_code == 404


def test_repo_summary_404_on_ownership_denied(client):
    # 다른 user_id를 가진 repo → 소유권 거부 → 404
    # Repo owned by different user → ownership denied → 404
    repo = _mock_repo(user_id=99)
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = repo
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal", return_value=_mock_session_ctx(db_mock)),
    ):
        resp = client.get("/api/issues/repo-summary?repo_id=1")
    assert resp.status_code == 404


def test_register_success_through_real_helper(client):
    # _get_analysis_and_repo 헬퍼 success path (line 54) 커버
    # Covers _get_analysis_and_repo helper success path (line 54)
    analysis = _mock_analysis()
    repo = _mock_repo()  # user_id=1 matches current_user.id=1
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.side_effect = [analysis, repo]
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal", return_value=_mock_session_ctx(db_mock)),
        patch("src.api.issue_registration.register_issue",
              new=AsyncMock(return_value={
                  "github_issue_number": 1,
                  "github_issue_url": "https://github.com/owner/repo/issues/1",
                  "state": "open",
              })),
    ):
        resp = client.post("/api/issues/register", json={
            "analysis_id": 10, "issue_type": "ai_suggestion",
            "suggestion_text": "text", "title": "T", "body": "B", "labels": [],
        })
    assert resp.status_code == 201


def test_repo_summary_success_through_real_helper(client):
    # _get_repo_or_404 헬퍼 success path (line 149) 커버
    # Covers _get_repo_or_404 helper success path (line 149)
    repo = _mock_repo()  # user_id=1 matches current_user.id=1
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.first.return_value = repo
    with (
        patch("src.api.issue_registration.get_current_user", return_value=_mock_user()),
        patch("src.api.issue_registration.SessionLocal", return_value=_mock_session_ctx(db_mock)),
        patch("src.api.issue_registration.get_repo_issue_summary",
              new=AsyncMock(return_value=[])),
    ):
        resp = client.get("/api/issues/repo-summary?repo_id=1")
    assert resp.status_code == 200
