import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import MagicMock, patch

import pytest  # noqa: E402 — 환경변수 setdefault 이후 import
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_get_analysis_detail():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
        id=1, commit_sha="abc", commit_message="feat: test",
        pr_number=1, score=85, grade="B",
        result={"breakdown": {}}, created_at=None)
    with patch("src.api.stats.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/api/analyses/1")
    assert r.status_code == 200
    assert r.json()["score"] == 85
    assert r.json()["commit_message"] == "feat: test"


def test_get_analysis_detail_404():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.api.stats.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/api/analyses/999")
    assert r.status_code == 404


def test_get_repo_stats():
    from datetime import datetime, timezone
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=1)
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
        MagicMock(score=85, grade="B", created_at=datetime(2026, 4, 1, tzinfo=timezone.utc)),
        MagicMock(score=70, grade="C", created_at=datetime(2026, 4, 2, tzinfo=timezone.utc)),
    ]
    with patch("src.api.stats.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/api/repos/owner%2Frepo/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["average_score"] == pytest.approx(77.5)
    assert data["total_analyses"] == 2
    assert len(data["trend"]) == 2
