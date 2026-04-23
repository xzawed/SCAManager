import hashlib
import hmac
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.main import app


client = TestClient(app)

SECRET = "test_webhook_secret"

def _sign(payload: bytes) -> str:
    mac = hmac.new(SECRET.encode(), payload, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")


def test_valid_push_event_returns_202():
    payload = json.dumps({"repository": {"full_name": "owner/repo"}, "after": "abc123"}).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.providers.github.run_analysis_pipeline"):
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "push",
                },
            )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_invalid_signature_returns_401():
    payload = b'{"test": true}'
    with patch("src.webhook.providers.github.settings") as mock_settings, patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": "sha256=invalidsignature",
                "X-GitHub-Event": "push",
            },
        )
    assert resp.status_code == 401


def test_ignored_event_returns_200():
    payload = json.dumps({"action": "labeled"}).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": _sign(payload),
                "X-GitHub-Event": "issues",
            },
        )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"


def test_closed_pr_action_ignored():
    payload = json.dumps({
        "action": "closed",
        "repository": {"full_name": "owner/repo"},
        "number": 1,
        "pull_request": {"head": {"sha": "abc123"}},
    }).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.providers.github.run_analysis_pipeline") as mock_pipeline:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )
    assert resp.status_code == 202
    assert resp.json()["status"] == "ignored"
    mock_pipeline.assert_not_called()


def test_opened_pr_action_accepted():
    payload = json.dumps({
        "action": "opened",
        "repository": {"full_name": "owner/repo"},
        "number": 1,
        "pull_request": {"head": {"sha": "abc123"}},
    }).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.providers.github.run_analysis_pipeline"):
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_webhook_uses_repo_specific_secret(client):
    """리포별 webhook_secret이 있으면 해당 시크릿으로 검증한다."""
    import hmac, hashlib
    from unittest.mock import patch, MagicMock

    payload = b'{"repository": {"full_name": "owner/repo-with-secret"}, "ref": "refs/heads/main", "after": "abc123", "commits": []}'
    repo_secret = "per-repo-secret-xyz"
    sig = "sha256=" + hmac.new(repo_secret.encode(), payload, hashlib.sha256).hexdigest()

    mock_repo = MagicMock()
    mock_repo.webhook_secret = repo_secret
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    with patch("src.webhook._helpers.SessionLocal", return_value=mock_db):
        with patch("src.webhook.providers.github.run_analysis_pipeline"):
            r = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
    assert r.status_code == 202


def test_webhook_falls_back_to_global_secret_for_legacy_repo(client):
    """webhook_secret이 없는 레거시 리포는 전역 시크릿으로 검증한다."""
    import hmac, hashlib
    from unittest.mock import patch, MagicMock

    payload = b'{"repository": {"full_name": "owner/legacy-repo"}, "ref": "refs/heads/main", "after": "abc123", "commits": []}'
    global_secret = "test_secret"  # conftest.py의 GITHUB_WEBHOOK_SECRET
    sig = "sha256=" + hmac.new(global_secret.encode(), payload, hashlib.sha256).hexdigest()

    mock_repo = MagicMock()
    mock_repo.webhook_secret = None   # 레거시 리포
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.query.return_value.filter_by.return_value.first.return_value = mock_repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    with patch("src.webhook._helpers.SessionLocal", return_value=mock_db):
        with patch("src.webhook.providers.github.run_analysis_pipeline"):
            r = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Event": "push",
                    "Content-Type": "application/json",
                },
            )
    assert r.status_code == 202
