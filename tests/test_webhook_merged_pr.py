"""tests/test_webhook_merged_pr.py

pull_request.closed + merged=true 이벤트 처리에 대한 선작성 테스트.
- _extract_closing_issue_numbers(): 정규식 파싱 단위 테스트
- _handle_merged_pr_event() / POST /webhooks/github 통합 테스트

구현 파일(router.py 수정 + issues.py)이 없으므로 일부 테스트는
pytest collect 또는 실행 시 ImportError/AttributeError → 정상 Red 상태.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import hashlib
import hmac
import json
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.webhook.router import _extract_closing_issue_numbers  # 구현 전 → ImportError (Red)

# ---------------------------------------------------------------------------
# 공통 픽스처
# ---------------------------------------------------------------------------

SECRET = "test_webhook_secret"
client = TestClient(app)


def _sign(payload: bytes) -> str:
    """HMAC-SHA256 서명 헬퍼 — 기존 test_webhook_router.py 와 동일 패턴."""
    mac = hmac.new(SECRET.encode(), payload, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """모든 테스트에서 환경변수와 settings mock을 자동 적용한다."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:ABC")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100123")


def _merged_pr_payload(body: str, merged: bool = True) -> bytes:
    """merged PR webhook payload 빌더."""
    return json.dumps({
        "action": "closed",
        "pull_request": {
            "merged": merged,
            "body": body,
            "head": {"sha": "deadbeef"},
        },
        "repository": {"full_name": "owner/repo"},
        "number": 10,
    }).encode()


# ---------------------------------------------------------------------------
# _extract_closing_issue_numbers 단위 테스트 (정규식 파싱)
# ---------------------------------------------------------------------------

def test_extract_closes_keyword():
    """'Closes #1' 형식에서 이슈 번호 1을 추출한다."""
    assert _extract_closing_issue_numbers("Closes #1") == [1]


def test_extract_closes_colon_keyword():
    """'closes: #2' 형식(콜론 포함)에서 이슈 번호 2를 추출한다."""
    assert _extract_closing_issue_numbers("closes: #2") == [2]


def test_extract_multiple_keywords_multiline():
    """'Fixes #3\\nResolves #4' 멀티라인 body에서 이슈 번호 [3, 4]를 추출한다."""
    assert _extract_closing_issue_numbers("Fixes #3\nResolves #4") == [3, 4]


def test_extract_bare_hash_ignored():
    """closing 키워드 없이 '#5'만 있는 경우 빈 리스트를 반환한다."""
    assert _extract_closing_issue_numbers("#5") == []


def test_extract_unrelated_text_ignored():
    """관련 없는 텍스트에서 빈 리스트를 반환한다."""
    assert _extract_closing_issue_numbers("unrelated text") == []


# ---------------------------------------------------------------------------
# POST /webhooks/github 통합 테스트 (merged PR 이벤트)
# ---------------------------------------------------------------------------

def test_merged_pr_with_closes_keyword_closes_issue():
    """'Closes #42' 키워드를 가진 merged PR 이벤트 수신 시 close_issue(issue_number=42)를 호출한다."""
    payload = _merged_pr_payload("Closes #42")

    with patch("src.webhook.router.settings") as mock_settings:
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.router.close_issue", new_callable=AsyncMock) as mock_close:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert resp.status_code == 202
    mock_close.assert_awaited_once()
    call_kwargs = mock_close.call_args.kwargs
    assert call_kwargs.get("issue_number") == 42
    assert call_kwargs.get("repo_full_name") == "owner/repo"


def test_merged_pr_fixes_keyword_case_insensitive():
    """소문자 'fixes #7' 키워드도 이슈 7을 닫도록 close_issue를 호출한다."""
    payload = _merged_pr_payload("fixes #7")

    with patch("src.webhook.router.settings") as mock_settings:
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.router.close_issue", new_callable=AsyncMock) as mock_close:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert resp.status_code == 202
    mock_close.assert_awaited_once()
    assert mock_close.call_args.kwargs.get("issue_number") == 7


def test_merged_pr_resolves_keyword_uppercase():
    """대문자 'RESOLVES #99' 키워드도 이슈 99를 닫도록 close_issue를 호출한다."""
    payload = _merged_pr_payload("RESOLVES #99")

    with patch("src.webhook.router.settings") as mock_settings:
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.router.close_issue", new_callable=AsyncMock) as mock_close:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert resp.status_code == 202
    mock_close.assert_awaited_once()
    assert mock_close.call_args.kwargs.get("issue_number") == 99


def test_merged_pr_without_merged_flag_is_ignored():
    """merged=False인 closed 이벤트는 close_issue를 호출하지 않는다."""
    payload = _merged_pr_payload("Closes #1", merged=False)

    with patch("src.webhook.router.settings") as mock_settings:
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.router.close_issue", new_callable=AsyncMock) as mock_close:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert resp.status_code == 202
    mock_close.assert_not_awaited()


def test_merged_pr_without_keyword_is_ignored():
    """closing 키워드 없는 merged PR은 close_issue를 호출하지 않는다."""
    payload = _merged_pr_payload("just a cleanup")

    with patch("src.webhook.router.settings") as mock_settings:
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.router.close_issue", new_callable=AsyncMock) as mock_close:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert resp.status_code == 202
    mock_close.assert_not_awaited()


def test_merged_pr_closes_multiple_issues():
    """'Closes #1, fixes #2' body에서 close_issue가 이슈 1과 2 각각 호출된다."""
    payload = _merged_pr_payload("Closes #1, fixes #2")

    with patch("src.webhook.router.settings") as mock_settings:
        mock_settings.github_webhook_secret = SECRET
        with patch("src.webhook.router.close_issue", new_callable=AsyncMock) as mock_close:
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )

    assert resp.status_code == 202
    assert mock_close.await_count == 2

    # 호출된 이슈 번호 집합이 {1, 2}와 일치해야 한다
    called_numbers = {call.kwargs.get("issue_number") for call in mock_close.call_args_list}
    assert called_numbers == {1, 2}


def test_merged_pr_close_api_failure_does_not_raise():
    """close_issue가 HTTPError를 발생시켜도 webhook은 202를 반환한다 (best-effort)."""
    payload = _merged_pr_payload("Closes #5")

    with patch("src.webhook.router.settings") as mock_settings:
        mock_settings.github_webhook_secret = SECRET
        with patch(
            "src.webhook.router.close_issue",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPError("connection failed"),
        ):
            resp = client.post(
                "/webhooks/github",
                content=payload,
                headers={
                    "X-Hub-Signature-256": _sign(payload),
                    "X-GitHub-Event": "pull_request",
                },
            )

    # 외부 API 실패와 무관하게 webhook 응답은 202여야 한다
    assert resp.status_code == 202
