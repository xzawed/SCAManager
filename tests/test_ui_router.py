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


def _ctx(db_mock):
    ctx = MagicMock()
    ctx.__enter__ = MagicMock(return_value=db_mock)
    ctx.__exit__ = MagicMock(return_value=False)
    return ctx


def test_overview_returns_html():
    mock_db = MagicMock()
    mock_db.query.return_value.order_by.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_repo_detail_returns_html():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=1, full_name="owner/repo")
    mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/owner%2Frepo")
    assert r.status_code == 200


def test_repo_detail_404():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        r = client.get("/repos/nope%2Frepo")
    assert r.status_code == 404


def test_settings_returns_html():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(id=1, full_name="owner/repo")
    from src.config_manager.manager import RepoConfigData
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.get_repo_config",
                   return_value=RepoConfigData(repo_full_name="owner/repo")):
            r = client.get("/repos/owner%2Frepo/settings")
    assert r.status_code == 200


def test_post_settings_redirects():
    # POST /repos/{repo}/settings 호출 시 upsert_repo_config에 n8n_webhook_url이 전달되고 303 리다이렉트 반환됨
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "auto",
                    "auto_approve_threshold": "85",
                    "auto_reject_threshold": "55",
                    "notify_chat_id": "-123",
                    "n8n_webhook_url": "http://n8n.local/webhook/abc",
                },
                follow_redirects=False,
            )
    # upsert_repo_config가 정확히 1회 호출됐는지 확인
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    # n8n_webhook_url 값이 RepoConfigData에 전달됐는지 확인
    assert called_config.n8n_webhook_url == "http://n8n.local/webhook/abc"
    # 응답이 리다이렉트(303)인지 확인
    assert r.status_code == 303


def test_post_settings_empty_n8n_url():
    # n8n_webhook_url을 비워서 전송 시 빈 문자열 또는 None이 RepoConfigData에 전달됨
    mock_db = MagicMock()
    with patch("src.ui.router.SessionLocal", return_value=_ctx(mock_db)):
        with patch("src.ui.router.upsert_repo_config") as mock_upsert:
            r = client.post(
                "/repos/owner%2Frepo/settings",
                data={
                    "gate_mode": "disabled",
                    "auto_approve_threshold": "75",
                    "auto_reject_threshold": "50",
                    "notify_chat_id": "",
                    "n8n_webhook_url": "",
                },
                follow_redirects=False,
            )
    assert mock_upsert.call_count == 1
    called_config = mock_upsert.call_args[0][1]
    # 빈 문자열이 RepoConfigData에 전달됐는지 확인 (None 또는 "" 모두 허용하지 않고 "" 그대로 확인)
    assert called_config.n8n_webhook_url == ""
