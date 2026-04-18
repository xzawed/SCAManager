"""TDD Red 테스트 — GitHub Issues 이벤트 webhook 수신 및 n8n 릴레이 검증.

구현 예정 변경 사항:
- src/constants.py: HANDLED_EVENTS에 "issues" 추가
- src/webhook/router.py: issues 이벤트 수신 시 notify_n8n_issue() BackgroundTask 등록
  - n8n_webhook_url이 있는 리포만 처리, 없으면 {"status": "ignored"}
  - HMAC 서명 검증은 기존 push/pull_request와 동일

이 테스트들은 구현 전 실패(Red) 상태여야 한다.
"""
import hashlib
import hmac
import json
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

SECRET = "test_secret"  # conftest.py의 GITHUB_WEBHOOK_SECRET과 동일


def _sign(payload: bytes, secret: str = SECRET) -> str:
    """GitHub webhook HMAC-SHA256 서명을 생성한다."""
    mac = hmac.new(secret.encode(), payload, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


def _issues_payload(
    repo_full_name: str = "owner/repo",
    action: str = "opened",
) -> bytes:
    """issues 이벤트 payload를 생성한다."""
    data = {
        "action": action,
        "issue": {
            "number": 42,
            "title": "버그 리포트",
            "state": "open",
            "body": "이슈 본문입니다.",
            "html_url": f"https://github.com/{repo_full_name}/issues/42",
            "user": {"login": "octocat"},
        },
        "sender": {"login": "octocat", "id": 1},
        "repository": {"full_name": repo_full_name},
    }
    return json.dumps(data).encode()


def _mock_repo(n8n_webhook_url: str | None = "https://n8n.example.com/webhook/abc") -> MagicMock:
    """RepoConfig를 모방하는 mock을 반환한다."""
    repo = MagicMock()
    repo.webhook_secret = None  # 전역 시크릿 사용
    repo.full_name = "owner/repo"
    return repo


def _mock_repo_config(n8n_webhook_url: str | None) -> MagicMock:
    """get_repo_config() 반환값을 모방하는 mock을 반환한다."""
    config = MagicMock()
    config.n8n_webhook_url = n8n_webhook_url
    return config


def _mock_db(repo: MagicMock | None = None) -> MagicMock:
    """SessionLocal context manager mock을 반환한다."""
    if repo is None:
        repo = _mock_repo()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = repo
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)
    return mock_db


# ── issues 이벤트 수신 테스트 ────────────────────────────────────────────────

def test_issues_event_with_valid_signature_returns_202():
    # issues 이벤트 + 유효 서명 + n8n_webhook_url 있는 리포 → 202 Accepted 반환
    payload = _issues_payload()
    repo_config = _mock_repo_config(n8n_webhook_url="https://n8n.example.com/webhook/abc")

    with patch("src.webhook.router.settings") as mock_settings, \
         patch("src.webhook.router.SessionLocal", return_value=_mock_db()), \
         patch("src.webhook.router.get_repo_config", return_value=repo_config), \
         patch("src.notifier.n8n.notify_n8n_issue") as mock_notify:
        mock_settings.github_webhook_secret = SECRET
        mock_settings.n8n_webhook_secret = ""
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": _sign(payload),
                "X-GitHub-Event": "issues",
            },
        )
    assert resp.status_code == 202
    assert resp.json().get("status") == "accepted"


def test_issues_event_registers_background_task_when_n8n_url_present():
    # issues 이벤트 + n8n_webhook_url 있는 리포 → BackgroundTask에 notify_n8n_issue 등록됨
    payload = _issues_payload()
    repo_config = _mock_repo_config(n8n_webhook_url="https://n8n.example.com/webhook/abc")

    registered_tasks = []

    def _capture_add_task(func, *args, **kwargs):
        registered_tasks.append(func)

    with patch("src.webhook.router.settings") as mock_settings, \
         patch("src.webhook.router.SessionLocal", return_value=_mock_db()), \
         patch("src.webhook.router.get_repo_config", return_value=repo_config):
        mock_settings.github_webhook_secret = SECRET
        mock_settings.n8n_webhook_secret = ""
        # BackgroundTasks.add_task를 패치해 등록 여부만 확인
        with patch("fastapi.BackgroundTasks.add_task", side_effect=_capture_add_task):
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "issues",
                },
            )
    assert resp.status_code == 202
    # notify_n8n_issue 관련 task가 등록되었는지 확인
    from src.notifier.n8n import notify_n8n_issue
    task_funcs = [f.__name__ if hasattr(f, "__name__") else str(f) for f in registered_tasks]
    assert any("notify_n8n_issue" in str(f) or "issue" in str(f).lower() for f in registered_tasks), \
        f"notify_n8n_issue task가 등록되지 않음. 등록된 tasks: {task_funcs}"


def test_issues_event_ignored_when_no_n8n_webhook_url():
    # issues 이벤트 + n8n_webhook_url 없는 리포 → 202이지만 status="ignored" 또는 task 미등록
    payload = _issues_payload()
    repo_config = _mock_repo_config(n8n_webhook_url=None)

    registered_tasks = []

    def _capture_add_task(func, *args, **kwargs):
        registered_tasks.append(func)

    with patch("src.webhook.router.settings") as mock_settings, \
         patch("src.webhook.router.SessionLocal", return_value=_mock_db()), \
         patch("src.webhook.router.get_repo_config", return_value=repo_config):
        mock_settings.github_webhook_secret = SECRET
        mock_settings.n8n_webhook_secret = ""
        with patch("fastapi.BackgroundTasks.add_task", side_effect=_capture_add_task):
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "issues",
                },
            )
    # 202여야 하고 notify_n8n_issue task는 등록되지 않아야 한다
    assert resp.status_code == 202
    from src.notifier.n8n import notify_n8n_issue
    assert not any("notify_n8n_issue" in str(f) or (hasattr(f, "__name__") and f.__name__ == "notify_n8n_issue")
                   for f in registered_tasks), \
        "n8n_webhook_url 없는 리포에서 notify_n8n_issue가 등록됨"


def test_issues_event_with_invalid_signature_returns_401():
    # issues 이벤트 + 무효 서명 → 401 Unauthorized
    payload = _issues_payload()
    with patch("src.webhook.router.settings") as mock_settings, \
         patch("src.webhook.router.SessionLocal", return_value=_mock_db()):
        mock_settings.github_webhook_secret = SECRET
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": "sha256=invalidsignature",
                "X-GitHub-Event": "issues",
            },
        )
    assert resp.status_code == 401


def test_unknown_event_returns_ignored():
    # 알 수 없는 이벤트 타입 → {"status": "ignored"} 반환
    payload = json.dumps({"repository": {"full_name": "owner/repo"}}).encode()
    with patch("src.webhook.router.settings") as mock_settings, \
         patch("src.webhook.router.SessionLocal", return_value=_mock_db()):
        mock_settings.github_webhook_secret = SECRET
        resp = client.post(
            "/webhooks/github",
            content=payload,
            headers={
                "X-Hub-Signature-256": _sign(payload),
                "X-GitHub-Event": "unknown_event_xyz",
            },
        )
    assert resp.status_code == 202
    assert resp.json().get("status") == "ignored"


def test_issues_event_in_handled_events():
    # HANDLED_EVENTS 상수에 "issues"가 포함되어야 한다
    from src.constants import HANDLED_EVENTS
    assert "issues" in HANDLED_EVENTS, \
        f'"issues"가 HANDLED_EVENTS에 없음: {HANDLED_EVENTS}'


# ── repo_token 전달 테스트 (Red phase) ─────────────────────────────────────────

def test_issues_event_passes_repo_token_to_notify():
    # issues 이벤트 수신 시 DB에서 owner.plaintext_token을 읽어 notify_n8n_issue에 repo_token으로 전달해야 한다
    payload = _issues_payload()
    repo_config = _mock_repo_config(n8n_webhook_url="https://n8n.example.com/webhook/abc")

    # Repository ORM mock: owner.plaintext_token = "ghp_owner_token"
    mock_owner = MagicMock()
    mock_owner.plaintext_token = "ghp_owner_token"
    mock_repo_obj = MagicMock()
    mock_repo_obj.full_name = "owner/repo"
    mock_repo_obj.owner = mock_owner
    mock_repo_obj.webhook_secret = None  # 전역 시크릿 사용 (MagicMock이 되면 HMAC 실패)

    # DB mock: query(Repository).filter(...).first() → mock_repo_obj
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_repo_obj
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=None)

    captured_kwargs = {}

    def _capture_add_task(func, *args, **kwargs):
        # notify_n8n_issue 관련 task의 kwargs를 캡처한다
        func_name = getattr(func, "__name__", "") or str(func)
        if "notify_n8n_issue" in func_name or "issue" in func_name.lower():
            captured_kwargs.update(kwargs)

    with patch("src.webhook.router.settings") as mock_settings, \
         patch("src.webhook.router.SessionLocal", return_value=mock_db), \
         patch("src.webhook.router.get_repo_config", return_value=repo_config):
        mock_settings.github_webhook_secret = SECRET
        mock_settings.n8n_webhook_secret = ""
        with patch("fastapi.BackgroundTasks.add_task", side_effect=_capture_add_task):
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "issues",
                },
            )

    assert resp.status_code == 202
    assert "repo_token" in captured_kwargs, \
        f"notify_n8n_issue 호출 시 repo_token kwarg가 전달되지 않음. 실제 kwargs: {captured_kwargs}"
    assert captured_kwargs["repo_token"] == "ghp_owner_token", \
        f"repo_token이 'ghp_owner_token'이어야 하지만 실제 값: {captured_kwargs.get('repo_token')!r}"
