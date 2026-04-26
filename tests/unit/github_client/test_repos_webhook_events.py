"""repos.py 웹훅 이벤트 관련 테스트 (Phase 12 T5).
Tests for webhook event subscription changes and update_webhook_events helper.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

TOKEN = "ghp_testtoken"
REPO = "owner/testrepo"
WEBHOOK_ID = 99887766


# ---------------------------------------------------------------------------
# 테스트 1: create_webhook 이 check_suite 이벤트를 포함해야 한다
# Test 1: create_webhook must include check_suite in the events list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_webhook_includes_check_suite_event():
    """create_webhook 이 check_suite 이벤트를 포함하는지 확인한다.
    Verify that create_webhook sends check_suite in the events list.
    """
    from src.github_client.repos import create_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 12345}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        await create_webhook(
            token=TOKEN,
            repo_full_name=REPO,
            webhook_url="https://example.com/webhooks/github",
            secret="test_secret_value",  # NOSONAR python:S6418 — test fixture, not a real secret
        )

    call_kwargs = mock_client.post.call_args
    posted_json = call_kwargs.kwargs["json"]
    events = posted_json["events"]

    # 4개 이벤트 모두 포함되어야 한다
    # All 4 events must be present.
    assert "push" in events
    assert "pull_request" in events
    assert "issues" in events
    assert "check_suite" in events, "check_suite 이벤트가 누락되었다 — Phase 12 CI 감지에 필수"


# ---------------------------------------------------------------------------
# 테스트 2: WEBHOOK_EVENTS 상수가 4개 이벤트를 정확히 포함해야 한다
# Test 2: WEBHOOK_EVENTS constant must contain exactly 4 expected events
# ---------------------------------------------------------------------------

def test_create_webhook_uses_webhook_events_constant():
    """WEBHOOK_EVENTS 상수가 정확히 4개의 이벤트를 담는지 검증한다.
    Verify WEBHOOK_EVENTS constant contains exactly the 4 expected events.
    """
    from src.github_client.repos import WEBHOOK_EVENTS

    expected = {"push", "pull_request", "issues", "check_suite"}
    assert set(WEBHOOK_EVENTS) == expected, (
        f"WEBHOOK_EVENTS 불일치 — 예상: {expected}, 실제: {set(WEBHOOK_EVENTS)}"
    )
    # 중복 없이 정확히 4개
    # Exactly 4 events, no duplicates.
    assert len(WEBHOOK_EVENTS) == 4


# ---------------------------------------------------------------------------
# 테스트 3: update_webhook_events 가 성공(200) 시 True 반환
# Test 3: update_webhook_events returns True on success (200)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_webhook_events_returns_true_on_success():
    """200 응답 시 update_webhook_events 가 True 를 반환하고 올바른 URL 로 PATCH 를 호출한다.
    update_webhook_events returns True on 200 and calls PATCH with the correct URL.
    """
    from src.github_client.repos import update_webhook_events

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.patch = AsyncMock(return_value=mock_resp)

        result = await update_webhook_events(
            token=TOKEN,
            repo_full_name=REPO,
            webhook_id=WEBHOOK_ID,
            events=["push", "pull_request", "issues", "check_suite"],
        )

    assert result is True

    # PATCH URL 검증 — /repos/{repo}/hooks/{id} 형태여야 한다
    # Verify PATCH URL — must be /repos/{repo}/hooks/{id}.
    call_args = mock_client.patch.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url", "")
    assert f"/repos/{REPO}/hooks/{WEBHOOK_ID}" in url, (
        f"PATCH URL이 올바르지 않다: {url}"
    )


# ---------------------------------------------------------------------------
# 테스트 4: update_webhook_events 가 오류(422) 시 False 반환
# Test 4: update_webhook_events returns False on error (422)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_webhook_events_returns_false_on_error():
    """422 응답 시 update_webhook_events 가 False 를 반환한다.
    update_webhook_events returns False when the API responds with 422.
    """
    from src.github_client.repos import update_webhook_events

    mock_resp = MagicMock()
    mock_resp.status_code = 422

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.patch = AsyncMock(return_value=mock_resp)

        result = await update_webhook_events(
            token=TOKEN,
            repo_full_name=REPO,
            webhook_id=WEBHOOK_ID,
            events=["push", "pull_request", "issues", "check_suite"],
        )

    assert result is False


# ---------------------------------------------------------------------------
# 테스트 5: update_webhook_events 가 올바른 events 목록을 전송한다
# Test 5: update_webhook_events sends the correct events list in PATCH body
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_webhook_events_sends_correct_body():
    """PATCH body 에 전달한 events 목록이 그대로 포함되어야 한다.
    The PATCH request body must contain exactly the events list passed in.
    """
    from src.github_client.repos import update_webhook_events

    events_to_send = ["push", "pull_request", "issues", "check_suite"]

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.patch = AsyncMock(return_value=mock_resp)

        await update_webhook_events(
            token=TOKEN,
            repo_full_name=REPO,
            webhook_id=WEBHOOK_ID,
            events=events_to_send,
        )

    call_kwargs = mock_client.patch.call_args.kwargs
    patched_json = call_kwargs["json"]
    assert patched_json["events"] == events_to_send
