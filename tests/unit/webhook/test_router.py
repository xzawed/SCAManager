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
        mock_settings.scamanager_self_analysis_disabled = False
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
        mock_settings.scamanager_self_analysis_disabled = False
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
    """webhook_secret이 없는 레거시 리포는 전역 시크릿으로 검증한다.

    PR B-2 (2026-05-02): 환경 의존성 제거 — repository_repo + settings 직접 mock.
    근본 원인: 일부 환경 (devcontainer 등) 에 `GITHUB_WEBHOOK_SECRET=dev_secret` 이
    export 되어 있어 conftest 의 `setdefault('test_secret')` 가 작동 안 함.
    fix: `_helpers.settings` 직접 mock 으로 환경 무관 secret 주입.
    """
    import hmac, hashlib
    from unittest.mock import patch, MagicMock

    payload = b'{"repository": {"full_name": "owner/legacy-repo"}, "ref": "refs/heads/main", "after": "abc123", "commits": []}'
    global_secret = "test_secret"
    sig = "sha256=" + hmac.new(global_secret.encode(), payload, hashlib.sha256).hexdigest()

    mock_repo = MagicMock()
    mock_repo.webhook_secret = None   # 레거시 리포 — fallback 경로 진입

    with patch("src.webhook._helpers.repository_repo.find_by_full_name", return_value=mock_repo), \
         patch("src.webhook._helpers.settings") as mock_helpers_settings, \
         patch("src.webhook.providers.github.run_analysis_pipeline"):
        mock_helpers_settings.github_webhook_secret = global_secret
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


def test_bot_sender_push_is_skipped():
    """봇 발신(sender.type == Bot) push → 202 skipped (bot_sender)."""
    data = {
        "repository": {"full_name": "owner/repo"},
        "sender": {"type": "Bot", "login": "renovate[bot]"},
        "after": "abc123",
    }
    payload = json.dumps(data).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, \
         patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        mock_settings.scamanager_self_analysis_disabled = False
        with patch("src.webhook.providers.github.run_analysis_pipeline") as mock_pipeline:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "push",
                },
            )
    assert resp.status_code == 202
    assert resp.json()["status"] == "skipped"
    assert resp.json()["reason"] == "bot_sender"
    mock_pipeline.assert_not_called()


def test_skip_ci_marker_push_is_skipped():
    """커밋 메시지에 [skip ci] 마커가 있으면 → 202 skipped (skip_marker)."""
    data = {
        "repository": {"full_name": "owner/repo"},
        "sender": {"type": "User", "login": "developer"},
        "head_commit": {"message": "chore: update deps [skip ci]"},
        "after": "abc123",
    }
    payload = json.dumps(data).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, \
         patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        mock_settings.scamanager_self_analysis_disabled = False
        with patch("src.webhook.providers.github.run_analysis_pipeline") as mock_pipeline:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "push",
                },
            )
    assert resp.status_code == 202
    assert resp.json()["status"] == "skipped"
    assert resp.json()["reason"] == "skip_marker"
    mock_pipeline.assert_not_called()


def test_self_analysis_disabled_skips_all():
    """scamanager_self_analysis_disabled=True 킬 스위치 → 202 skipped (self_analysis_disabled)."""
    data = {
        "repository": {"full_name": "owner/repo"},
        "sender": {"type": "User", "login": "developer"},
        "after": "abc123",
    }
    payload = json.dumps(data).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, \
         patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        mock_settings.scamanager_self_analysis_disabled = True
        with patch("src.webhook.providers.github.run_analysis_pipeline") as mock_pipeline:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "push",
                },
            )
    assert resp.status_code == 202
    assert resp.json()["status"] == "skipped"
    assert resp.json()["reason"] == "self_analysis_disabled"
    mock_pipeline.assert_not_called()


def test_loop_guard_handles_head_commit_none_without_npe():
    """Phase 4 회고 — head_commit=None 페이로드 시 _loop_guard_check 가
    AttributeError 던지지 않고 graceful 진행 (회귀 방지).

    GitHub 의 일부 push 이벤트(브랜치 삭제 등)에서 head_commit 키 값이 None 으로
    내려오는 사례가 있었으며, 기존 `data.get("head_commit", {}).get(...)` 체이닝은
    값이 None 이면 NPE. pull_request 키도 동일 패턴 보호 필요.
    """
    data = {
        "repository": {"full_name": "owner/repo"},
        "sender": {"type": "User", "login": "developer"},
        "after": "abc123",
        "head_commit": None,         # NPE 트리거 (회고 §발견된 잔여 결함)
        "pull_request": None,         # 두 번째 분기 동일 보호 검증
    }
    payload = json.dumps(data).encode()
    with patch("src.webhook.providers.github.settings") as mock_settings, \
         patch("src.webhook._helpers.settings") as mock_helpers_settings:
        mock_helpers_settings.github_webhook_secret = SECRET
        mock_settings.github_webhook_secret = SECRET
        mock_settings.scamanager_self_analysis_disabled = False
        with patch("src.webhook.providers.github.run_analysis_pipeline") as mock_pipeline:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "push",
                },
            )
    # NPE 가 났다면 500 응답 — 200/202 범위면 graceful 진행
    # 정확한 status 는 후속 분기에 따라 다르나 5xx 는 회귀 신호
    assert resp.status_code < 500, (
        f"head_commit=None NPE 회귀 — got {resp.status_code}: {resp.text}"
    )
    # 정상 흐름이면 파이프라인이 등록되어야 함 (skip 마커 없음)
    if resp.status_code == 202 and resp.json().get("status") == "accepted":
        mock_pipeline.assert_called_once()
