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
                repo_full_name="owner/repo", approve_mode="auto",
                approve_threshold=80, reject_threshold=45,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None, auto_merge=False,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "approve_mode": "auto", "approve_threshold": 80, "reject_threshold": 45,
            })
    assert r.status_code == 200
    assert r.json()["approve_mode"] == "auto"


# --- API auto_merge 테스트 (Red: RepoConfigUpdate와 응답에 auto_merge 필드가 아직 없음) ---

def test_put_repo_config_with_auto_merge_true():
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="auto",
                approve_threshold=80, reject_threshold=45,
                pr_review_comment=True, merge_threshold=80,
                notify_chat_id=None, n8n_webhook_url=None,
                auto_merge=True,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "approve_mode": "auto",
                "approve_threshold": 80,
                "reject_threshold": 45,
                "auto_merge": True,
                "merge_threshold": 80,
            })
    assert r.status_code == 200
    assert r.json()["auto_merge"] is True


def test_put_repo_config_auto_merge_defaults_false():
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="disabled",
                approve_threshold=75, reject_threshold=50,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None,
                auto_merge=False,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "approve_mode": "disabled",
            })
    assert r.status_code == 200
    assert r.json()["auto_merge"] is False


# --- 누락 필드 버그 수정 테스트 (discord/slack/webhook/email) ---

def test_update_config_discord_webhook_url_passed():
    """PUT /config 에 discord_webhook_url 전달 시 upsert_repo_config에 전달되어야 한다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="disabled",
                approve_threshold=75, reject_threshold=50,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None,
                discord_webhook_url="https://discord.com/api/webhooks/test",
                slack_webhook_url=None, custom_webhook_url=None,
                email_recipients=None, auto_merge=False,
            )
            client.put("/api/repos/owner%2Frepo/config", json={
                "discord_webhook_url": "https://discord.com/api/webhooks/test",
            })
    called_data = mock_upsert.call_args[0][1]
    assert called_data.discord_webhook_url == "https://discord.com/api/webhooks/test"


def test_update_config_slack_webhook_url_passed():
    """PUT /config 에 slack_webhook_url 전달 시 upsert_repo_config에 전달되어야 한다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="disabled",
                approve_threshold=75, reject_threshold=50,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None,
                discord_webhook_url=None,
                slack_webhook_url="https://hooks.slack.com/test",
                custom_webhook_url=None, email_recipients=None, auto_merge=False,
            )
            client.put("/api/repos/owner%2Frepo/config", json={
                "slack_webhook_url": "https://hooks.slack.com/test",
            })
    called_data = mock_upsert.call_args[0][1]
    assert called_data.slack_webhook_url == "https://hooks.slack.com/test"


def test_update_config_custom_webhook_url_passed():
    """PUT /config 에 custom_webhook_url 전달 시 upsert_repo_config에 전달되어야 한다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="disabled",
                approve_threshold=75, reject_threshold=50,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None,
                discord_webhook_url=None, slack_webhook_url=None,
                custom_webhook_url="https://my.server/hook",
                email_recipients=None, auto_merge=False,
            )
            client.put("/api/repos/owner%2Frepo/config", json={
                "custom_webhook_url": "https://my.server/hook",
            })
    called_data = mock_upsert.call_args[0][1]
    assert called_data.custom_webhook_url == "https://my.server/hook"


def test_update_config_email_recipients_passed():
    """PUT /config 에 email_recipients 전달 시 upsert_repo_config에 전달되어야 한다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="disabled",
                approve_threshold=75, reject_threshold=50,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None,
                discord_webhook_url=None, slack_webhook_url=None,
                custom_webhook_url=None, email_recipients="a@b.com",
                auto_merge=False,
            )
            client.put("/api/repos/owner%2Frepo/config", json={
                "email_recipients": "a@b.com",
            })
    called_data = mock_upsert.call_args[0][1]
    assert called_data.email_recipients == "a@b.com"


# ---------------------------------------------------------------------------
# PR Gate 3-옵션 분리 재설계 — API 신규 필드 테스트 (Red)
#
# 신규 필드: approve_mode, approve_threshold, reject_threshold,
#            pr_review_comment, merge_threshold
# 기존 필드 rename: gate_mode → approve_mode,
#                   auto_approve_threshold → approve_threshold,
#                   auto_reject_threshold → reject_threshold
# ---------------------------------------------------------------------------

def test_config_update_with_approve_mode():
    """PUT /config 에 approve_mode 전달 시 응답 JSON에 포함되어야 한다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo",
                approve_mode="auto",
                approve_threshold=80,
                reject_threshold=45,
                notify_chat_id=None,
                n8n_webhook_url=None,
                auto_merge=False,
                pr_review_comment=True,
                merge_threshold=75,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "approve_mode": "auto",
                "approve_threshold": 80,
                "reject_threshold": 45,
            })
    assert r.status_code == 200
    assert r.json()["approve_mode"] == "auto"


def test_config_update_with_pr_review_comment_false():
    """PUT /config 에 pr_review_comment=False 전달 시 upsert_repo_config에 전달되어야 한다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo",
                approve_mode="disabled",
                approve_threshold=75,
                reject_threshold=50,
                notify_chat_id=None,
                n8n_webhook_url=None,
                auto_merge=False,
                pr_review_comment=False,
                merge_threshold=75,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "pr_review_comment": False,
            })
    assert r.status_code == 200
    assert r.json()["pr_review_comment"] is False


def test_config_update_with_merge_threshold():
    """PUT /config 에 merge_threshold 전달 시 upsert_repo_config에 전달되어야 한다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo",
                approve_mode="disabled",
                approve_threshold=75,
                reject_threshold=50,
                notify_chat_id=None,
                n8n_webhook_url=None,
                auto_merge=True,
                pr_review_comment=True,
                merge_threshold=85,
            )
            client.put("/api/repos/owner%2Frepo/config", json={
                "auto_merge": True,
                "merge_threshold": 85,
            })
    called_data = mock_upsert.call_args[0][1]
    assert called_data.merge_threshold == 85


def test_config_response_includes_new_fields():
    """GET/PUT 응답에 pr_review_comment, merge_threshold, approve_mode가 포함된다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_db = MagicMock()
            mock_cls.return_value = _make_session_mock(mock_db)
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo",
                approve_mode="semi-auto",
                approve_threshold=70,
                reject_threshold=40,
                notify_chat_id="-100999",
                n8n_webhook_url=None,
                auto_merge=True,
                pr_review_comment=True,
                merge_threshold=80,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "approve_mode": "semi-auto",
                "approve_threshold": 70,
                "reject_threshold": 40,
                "auto_merge": True,
                "pr_review_comment": True,
                "merge_threshold": 80,
            })
    assert r.status_code == 200
    body = r.json()
    assert "approve_mode" in body
    assert "pr_review_comment" in body
    assert "merge_threshold" in body
    assert body["approve_mode"] == "semi-auto"
    assert body["pr_review_comment"] is True
    assert body["merge_threshold"] == 80


def test_config_update_approve_threshold_passed_to_upsert():
    """PUT /config 에 approve_threshold 전달 시 RepoConfigData에 올바르게 전달된다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo",
                approve_mode="auto",
                approve_threshold=90,
                reject_threshold=60,
                notify_chat_id=None, n8n_webhook_url=None,
                auto_merge=False, pr_review_comment=True, merge_threshold=75,
            )
            client.put("/api/repos/owner%2Frepo/config", json={
                "approve_mode": "auto",
                "approve_threshold": 90,
                "reject_threshold": 60,
            })
    called_data = mock_upsert.call_args[0][1]
    assert called_data.approve_threshold == 90
    assert called_data.reject_threshold == 60


# ── DELETE /api/repos/{repo} 테스트 ──────────────────────────

def test_delete_repo_api_success():
    """API로 리포 삭제 시 연관 데이터 정리 후 200 JSON 반환."""
    mock_repo = MagicMock(id=1, full_name="owner/repo", webhook_id=999)
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo
    mock_db.query.return_value.filter.return_value.all.return_value = []

    with patch("src.api.repos.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.delete("/api/repos/owner%2Frepo")

    assert r.status_code == 200
    body = r.json()
    assert body["deleted"] is True
    assert body["repo_full_name"] == "owner/repo"
    assert body["webhook_id"] == 999
    mock_db.delete.assert_called_once_with(mock_repo)
    mock_db.commit.assert_called()


def test_delete_repo_api_404():
    """존재하지 않는 리포 삭제 → 404."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None
    with patch("src.api.repos.SessionLocal", return_value=_make_session_mock(mock_db)):
        r = client.delete("/api/repos/nope%2Frepo")
    assert r.status_code == 404
    mock_db.delete.assert_not_called()


# ---------------------------------------------------------------------------
# P1 — approve_threshold < reject_threshold → 422 검증
# ---------------------------------------------------------------------------

def test_put_config_returns_422_when_approve_threshold_less_than_reject():
    """approve_threshold < reject_threshold 이면 pydantic이 422를 반환해야 한다."""
    r = client.put("/api/repos/owner%2Frepo/config", json={
        "approve_threshold": 40,
        "reject_threshold": 60,
    })
    assert r.status_code == 422


def test_put_config_returns_200_when_thresholds_equal():
    """approve_threshold == reject_threshold 이면 정상 저장된다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="disabled",
                approve_threshold=60, reject_threshold=60,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None,
                discord_webhook_url=None, slack_webhook_url=None,
                custom_webhook_url=None, email_recipients=None, auto_merge=False,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "approve_threshold": 60,
                "reject_threshold": 60,
            })
    assert r.status_code == 200


def test_config_update_with_commit_comment_and_create_issue():
    """PUT /config 에 commit_comment/create_issue 전달 시 upsert에 전달되고 응답에 포함된다."""
    with patch("src.api.repos.SessionLocal") as mock_cls:
        with patch("src.api.repos.upsert_repo_config") as mock_upsert:
            mock_cls.return_value = _make_session_mock(MagicMock())
            mock_upsert.return_value = MagicMock(
                repo_full_name="owner/repo", approve_mode="disabled",
                approve_threshold=75, reject_threshold=50,
                pr_review_comment=True, merge_threshold=75,
                notify_chat_id=None, n8n_webhook_url=None,
                discord_webhook_url=None, slack_webhook_url=None,
                custom_webhook_url=None, email_recipients=None, auto_merge=False,
                commit_comment=True, create_issue=True,
            )
            r = client.put("/api/repos/owner%2Frepo/config", json={
                "commit_comment": True,
                "create_issue": True,
            })
    assert r.status_code == 200
    assert r.json()["commit_comment"] is True
    assert r.json()["create_issue"] is True
    called_data = mock_upsert.call_args[0][1]
    assert called_data.commit_comment is True
    assert called_data.create_issue is True
