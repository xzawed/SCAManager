import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("API_KEY", "")

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)


def _make_session_mock(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_get_repos_returns_list():
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.all.return_value = [
        MagicMock(id=1, full_name="owner/repo1", created_at=None),
    ]
    with patch("src.api.repos.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get("/api/repos")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_repo_analyses_returns_list():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=1)
    mock_db.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
        MagicMock(id=1, commit_sha="abc", pr_number=1, score=85, grade="B", created_at=None),
    ]
    with patch("src.api.repos.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get("/api/repos/owner%2Frepo1/analyses")
    assert r.status_code == 200


def test_get_repo_analyses_404():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.api.repos.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.get("/api/repos/nope%2Frepo/analyses")
    assert r.status_code == 404


def test_put_repo_config():
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", gate_mode="auto",
                auto_approve_threshold=80, auto_reject_threshold=45,
                notify_chat_id=None, n8n_webhook_url=None
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "gate_mode": "auto", "auto_approve_threshold": 80, "auto_reject_threshold": 45,
            })
    assert r.status_code == 200
    assert r.json()["gate_mode"] == "auto"


# --- API auto_merge 테스트 (Red: RepoConfigUpdate와 응답에 auto_merge 필드가 아직 없음) ---

def test_put_repo_config_with_auto_merge_true():
    # PUT /api/repos/{repo}/config 에 auto_merge=True 전달 시 응답 JSON에 포함되는지 검증
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", gate_mode="auto",
                auto_approve_threshold=80, auto_reject_threshold=45,
                notify_chat_id=None, n8n_webhook_url=None,
                auto_merge=True,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "gate_mode": "auto",
                "auto_approve_threshold": 80,
                "auto_reject_threshold": 45,
                "auto_merge": True,
            })
    assert r.status_code == 200
    assert r.json()["auto_merge"] is True


def test_put_repo_config_auto_merge_defaults_false():
    # auto_merge 없이 PUT 요청 시 응답의 auto_merge가 False인지 검증
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", gate_mode="disabled",
                auto_approve_threshold=75, auto_reject_threshold=50,
                notify_chat_id=None, n8n_webhook_url=None,
                auto_merge=False,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "gate_mode": "disabled",
            })
    assert r.status_code == 200
    assert r.json()["auto_merge"] is False
