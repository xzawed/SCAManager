"""telegram_post_message — 봇 차단 silent skip + streak guard 회귀 가드.

Cycle 78 PR 2 — 🅒 P0-1 (5+1 cross-verify 결과).
봇 차단 (403 Forbidden) 시 silent skip + WARNING + 5회 연속 시 streak WARNING.
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notifier import telegram as telegram_module


@pytest.fixture(autouse=True)
def _reset_streak():
    """테스트 격리 — 모듈 레벨 streak 카운터 reset."""
    telegram_module._telegram_bot_blocked_streak = 0
    yield
    telegram_module._telegram_bot_blocked_streak = 0


def _make_response(status_code: int):
    """httpx Response mock — status_code + raise_for_status no-op."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_403_silent_skip_no_raise(caplog):
    """403 Forbidden 응답 시 silent skip — raise_for_status X + WARNING 로그."""
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_make_response(403))
    with patch("src.notifier.telegram.get_http_client", return_value=fake_client):
        with caplog.at_level(logging.WARNING, logger="src.notifier.telegram"):
            # raise X — silent skip
            await telegram_module.telegram_post_message(
                bot_token="fake-token", chat_id="123", payload={"text": "hi"},
            )
    msgs = [r.getMessage() for r in caplog.records]
    assert any("403" in m and "silent skip" in m for m in msgs), \
        "403 silent skip WARNING 의무"


@pytest.mark.asyncio
async def test_403_increments_streak(caplog):
    """403 응답 1회 = streak +1. threshold 미만 = streak WARNING X."""
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_make_response(403))
    with patch("src.notifier.telegram.get_http_client", return_value=fake_client):
        with caplog.at_level(logging.WARNING, logger="src.notifier.telegram"):
            await telegram_module.telegram_post_message(
                bot_token="fake-token", chat_id="123", payload={"text": "hi"},
            )
    assert telegram_module._telegram_bot_blocked_streak == 1
    msgs = [r.getMessage() for r in caplog.records]
    # streak WARNING (5회 연속) 미발화
    assert not any("streak=" in m for m in msgs)


@pytest.mark.asyncio
async def test_403_streak_threshold_emits_warning_and_resets(caplog):
    """403 5회 연속 = streak WARNING + reset (재 alert 방지)."""
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_make_response(403))
    with patch("src.notifier.telegram.get_http_client", return_value=fake_client):
        with caplog.at_level(logging.WARNING, logger="src.notifier.telegram"):
            for _ in range(5):
                await telegram_module.telegram_post_message(
                    bot_token="fake-token", chat_id="123", payload={"text": "hi"},
                )
    msgs = [r.getMessage() for r in caplog.records]
    assert any("streak=5" in m for m in msgs), \
        "5회 연속 403 시 streak=5 WARNING 의무"
    # reset (재 alert 방지)
    assert telegram_module._telegram_bot_blocked_streak == 0


@pytest.mark.asyncio
async def test_200_resets_streak():
    """정상 응답 (200) 시 streak reset."""
    telegram_module._telegram_bot_blocked_streak = 3  # 사전 누적
    fake_client = MagicMock()
    fake_client.post = AsyncMock(return_value=_make_response(200))
    with patch("src.notifier.telegram.get_http_client", return_value=fake_client):
        await telegram_module.telegram_post_message(
            bot_token="fake-token", chat_id="123", payload={"text": "hi"},
        )
    assert telegram_module._telegram_bot_blocked_streak == 0


@pytest.mark.asyncio
async def test_200_no_warning(caplog):
    """정상 응답 (200) 시 WARNING 없음 + raise_for_status no-op."""
    fake_client = MagicMock()
    fake_resp = _make_response(200)
    fake_client.post = AsyncMock(return_value=fake_resp)
    with patch("src.notifier.telegram.get_http_client", return_value=fake_client):
        with caplog.at_level(logging.WARNING, logger="src.notifier.telegram"):
            await telegram_module.telegram_post_message(
                bot_token="fake-token", chat_id="123", payload={"text": "hi"},
            )
    msgs = [r.getMessage() for r in caplog.records]
    assert not any("403" in m for m in msgs)
    fake_resp.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_500_still_raises(caplog):
    """500 Internal Server Error = silent skip 영역 X — raise_for_status 발화."""
    fake_client = MagicMock()
    fake_resp = _make_response(500)
    fake_resp.raise_for_status.side_effect = Exception("500 server error")
    fake_client.post = AsyncMock(return_value=fake_resp)
    with patch("src.notifier.telegram.get_http_client", return_value=fake_client):
        with pytest.raises(Exception, match="500"):
            await telegram_module.telegram_post_message(
                bot_token="fake-token", chat_id="123", payload={"text": "hi"},
            )
    # 500 = streak 미증가 (403 만 카운트)
    assert telegram_module._telegram_bot_blocked_streak == 0


@pytest.mark.asyncio
async def test_403_then_200_resets_streak(caplog):
    """403 후 200 = streak reset (정상 복구)."""
    fake_client = MagicMock()
    # 첫 호출 403, 두 번째 호출 200
    responses = [_make_response(403), _make_response(200)]
    fake_client.post = AsyncMock(side_effect=responses)
    with patch("src.notifier.telegram.get_http_client", return_value=fake_client):
        with caplog.at_level(logging.WARNING, logger="src.notifier.telegram"):
            # 첫 호출 = 403 silent skip
            await telegram_module.telegram_post_message(
                bot_token="fake-token", chat_id="123", payload={"text": "hi"},
            )
            assert telegram_module._telegram_bot_blocked_streak == 1
            # 두 번째 호출 = 200 정상 → streak reset
            await telegram_module.telegram_post_message(
                bot_token="fake-token", chat_id="123", payload={"text": "hi"},
            )
    assert telegram_module._telegram_bot_blocked_streak == 0
