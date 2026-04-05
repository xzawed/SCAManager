import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

APPROVE = {"update_id": 1, "callback_query": {"id": "c1", "from": {"id": 1, "username": "john"},
            "data": "gate:approve:42", "message": {"message_id": 1, "chat": {"id": -1}}}}
REJECT = {"update_id": 2, "callback_query": {"id": "c2", "from": {"id": 1, "username": "john"},
           "data": "gate:reject:42", "message": {"message_id": 1, "chat": {"id": -1}}}}
OTHER = {"update_id": 3, "callback_query": {"id": "c3", "from": {"id": 1, "username": "john"},
          "data": "other:action", "message": {"message_id": 1, "chat": {"id": -1}}}}

def test_approve_returns_200():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=APPROVE)
    assert r.status_code == 200

def test_reject_returns_200():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock):
        r = client.post("/api/webhook/telegram", json=REJECT)
    assert r.status_code == 200

def test_non_gate_returns_200():
    r = client.post("/api/webhook/telegram", json=OTHER)
    assert r.status_code == 200

def test_no_callback_query_returns_200():
    r = client.post("/api/webhook/telegram", json={"update_id": 1})
    assert r.status_code == 200

def test_gate_callback_called_with_correct_args():
    with patch("src.webhook.router.handle_gate_callback", new_callable=AsyncMock) as mock_h:
        client.post("/api/webhook/telegram", json=APPROVE)
    mock_h.assert_called_once()
    kw = mock_h.call_args.kwargs
    assert kw["analysis_id"] == 42
    assert kw["decision"] == "approve"
    assert kw["decided_by"] == "john"
