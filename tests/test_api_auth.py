import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "test-api-key-12345")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.api.auth import require_api_key

app = FastAPI()

@app.get("/protected", dependencies=[require_api_key])
def protected():
    return {"data": "secret"}

client = TestClient(app, raise_server_exceptions=False)

_TEST_KEY = "test-api-key-12345"


def test_valid_key_allowed(monkeypatch):
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    r = client.get("/protected", headers={"X-API-Key": _TEST_KEY})
    assert r.status_code == 200

def test_missing_key_rejected(monkeypatch):
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    r = client.get("/protected")
    assert r.status_code == 401

def test_wrong_key_rejected(monkeypatch):
    monkeypatch.setattr("src.api.auth.settings.api_key", _TEST_KEY)
    r = client.get("/protected", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401

def test_no_api_key_config_allows_all(monkeypatch):
    monkeypatch.setattr("src.api.auth.settings.api_key", "")
    r = client.get("/protected")
    assert r.status_code == 200
