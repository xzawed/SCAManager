"""TDD Red 단계 — src/webhook/loop_guard.py 테스트.
TDD Red phase — tests for src/webhook/loop_guard.py.

구현 파일이 아직 존재하지 않으므로 모든 테스트는 ImportError로 실패해야 한다.
All tests must fail with ImportError because the implementation file does not exist yet.
"""

import time
from unittest.mock import patch

from src.webhook.loop_guard import (
    BotInteractionLimiter,
    has_skip_marker,
    is_bot_sender,
)


# ── is_bot_sender ──────────────────────────────────────────────────────────────


def test_is_bot_sender_returns_true_for_unlisted_bot():
    # sender.type == "Bot" 이고 login이 BOT_LOGIN_WHITELIST에 없으면 True 반환
    # Returns True when sender.type is "Bot" and login is not in BOT_LOGIN_WHITELIST
    data = {"sender": {"type": "Bot", "login": "renovate[bot]"}}
    assert is_bot_sender(data) is True


def test_is_bot_sender_returns_false_for_whitelisted_bot():
    # sender.type == "Bot" 이어도 BOT_LOGIN_WHITELIST에 있으면 False 반환 (허용 봇)
    # Returns False when sender is a whitelisted bot (e.g. github-actions[bot])
    data = {"sender": {"type": "Bot", "login": "github-actions[bot]"}}
    assert is_bot_sender(data) is False


def test_is_bot_sender_returns_false_when_sender_missing():
    # sender 필드가 없으면 False 반환 (안전 기본값)
    # Returns False when the sender field is absent (safe default)
    data = {"repository": {"full_name": "owner/repo"}}
    assert is_bot_sender(data) is False


# ── has_skip_marker ────────────────────────────────────────────────────────────


def test_has_skip_marker_detects_skip_ci():
    # "[skip ci]" 마커가 커밋 메시지에 포함되면 True 반환
    # Returns True when "[skip ci]" marker is present in the commit message
    assert has_skip_marker("feat: add foo [skip ci]") is True


def test_has_skip_marker_detects_skip_sca():
    # "[skip-sca]" 마커가 커밋 메시지에 포함되면 True 반환
    # Returns True when "[skip-sca]" marker is present in the commit message
    assert has_skip_marker("chore: update deps [skip-sca]") is True


def test_has_skip_marker_returns_false_for_normal_message():
    # 마커가 없는 일반 커밋 메시지는 False 반환
    # Returns False for a plain commit message that contains no skip markers
    assert has_skip_marker("normal commit message") is False


# ── BotInteractionLimiter ──────────────────────────────────────────────────────


def test_bot_interaction_limiter_allows_up_to_max():
    # MAX_BOT_EVENTS_PER_HOUR(6)번째 이벤트까지 allow()가 True를 반환해야 한다
    # allow() returns True for each of the first MAX_BOT_EVENTS_PER_HOUR (6) calls
    limiter = BotInteractionLimiter()
    repo = "owner/repo"
    results = [limiter.allow(repo) for _ in range(6)]
    assert results == [True] * 6


def test_bot_interaction_limiter_blocks_on_exceeded():
    # MAX_BOT_EVENTS_PER_HOUR(6) 초과 시 7번째 allow()는 False를 반환해야 한다
    # allow() returns False on the 7th call when the hourly limit is exceeded
    limiter = BotInteractionLimiter()
    repo = "owner/repo"
    for _ in range(6):
        limiter.allow(repo)
    assert limiter.allow(repo) is False


def test_bot_interaction_limiter_expires_old_events():
    # 1시간(3600초)이 지난 이벤트는 sliding window에서 제외되어 다시 허용된다
    # Events older than 3600 seconds are evicted from the window and no longer counted
    limiter = BotInteractionLimiter()
    repo = "owner/repo"

    # 현재 시각을 t=0으로 고정하고 6번 이벤트를 채운다
    # Fill up 6 events at t=0
    base_time = 1_000_000.0
    with patch("time.time", return_value=base_time):
        for _ in range(6):
            limiter.allow(repo)

    # t=0에서 7번째 시도 → 차단
    # 7th attempt at t=0 must be blocked
    with patch("time.time", return_value=base_time):
        assert limiter.allow(repo) is False

    # 3601초 후 — 기존 이벤트 전부 만료 → 다시 허용
    # After 3601 seconds all previous events have expired → allowed again
    with patch("time.time", return_value=base_time + 3601):
        assert limiter.allow(repo) is True
