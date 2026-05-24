# tests/unit/api/test_issue_registration_api.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.auth.session import CurrentUser


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
