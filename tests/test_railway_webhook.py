import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

_TOKEN = "abc123valid_token_hex_32chars_xxxxxx"

_PAYLOAD = json.dumps({
    "type": "DEPLOY",
    "status": "BUILD_FAILED",
    "timestamp": "2026-04-20T10:00:00Z",
    "deployment": {
        "id": "deploy-abc",
        "meta": {
            "commitSha": "deadbeef",
            "commitMessage": "feat: something",
            "repo": "owner/repo",
        },
    },
    "project": {"id": "proj-1", "name": "my-project"},
    "environment": {"name": "production"},
}).encode()


def _mock_config(alerts=True, token=_TOKEN, api_token=None):
    c = MagicMock()
    c.railway_deploy_alerts = alerts
    c.railway_webhook_token = token
    c.railway_api_token = api_token
    c.repo_full_name = "owner/repo"
    return c


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def _db_with_config(config_mock):
    """RepoConfig query → config_mock, Repository/User queries → None."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.side_effect = [
        config_mock,
        None,  # Repository (user_id 없음 → github_token=settings fallback)
    ]
    return mock_db


def test_invalid_token_returns_404():
    """토큰 불일치 시 404 를 반환해야 한다."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.webhook.providers.railway.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post("/webhooks/railway/wrongtoken", content=_PAYLOAD)
    assert resp.status_code == 404


def test_alerts_disabled_returns_200_ignored():
    """`railway_deploy_alerts=False` 이면 200 ignored 를 반환해야 한다."""
    mock_db = _db_with_config(_mock_config(alerts=False))
    with patch("src.webhook.providers.railway.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post(f"/webhooks/railway/{_TOKEN}", content=_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_success_status_returns_200_ignored():
    """`status=SUCCESS` 이벤트는 200 ignored 를 반환해야 한다."""
    payload = json.dumps({
        "type": "DEPLOY", "status": "SUCCESS", "timestamp": "T",
        "deployment": {"id": "d1", "meta": {}},
        "project": {}, "environment": {},
    }).encode()
    mock_db = _db_with_config(_mock_config())
    with patch("src.webhook.providers.railway.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post(f"/webhooks/railway/{_TOKEN}", content=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"


def test_build_failed_returns_202_accepted():
    """빌드 실패 이벤트는 202 accepted 를 반환해야 한다."""
    mock_db = _db_with_config(_mock_config())
    with patch("src.webhook.providers.railway.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.webhook.providers.railway._handle_railway_deploy_failure", new_callable=AsyncMock):
            resp = client.post(f"/webhooks/railway/{_TOKEN}", content=_PAYLOAD)
    assert resp.status_code == 202
    assert resp.json()["status"] == "accepted"


def test_non_deploy_type_returns_200_ignored():
    """type != DEPLOY 이면 200 ignored."""
    payload = json.dumps({"type": "BUILD", "status": "FAILED"}).encode()
    mock_db = _db_with_config(_mock_config())
    with patch("src.webhook.providers.railway.SessionLocal", return_value=_ctx(mock_db)):
        resp = client.post(f"/webhooks/railway/{_TOKEN}", content=payload)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ignored"
