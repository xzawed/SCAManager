"""_loop_guard_check 정책 변경 — 봇만 rate-limit, 사람은 무제한 통과 (TDD Red).

Tests for _loop_guard_check policy change: Layer 3-b rate limit applies
only to whitelisted bots (sender.type=="Bot" AND login in BOT_LOGIN_WHITELIST).
Human senders (sender.type=="User" or missing sender) bypass the rate limit.

Layer 1 (kill-switch), Layer 2 (non-whitelisted bot block), and Layer 3-a
(skip marker) behavior must remain unchanged.
"""
# pylint: disable=redefined-outer-name,import-outside-toplevel
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

# src 임포트 전 환경변수 주입 필수 — Settings()는 import 시점에 인스턴스화됨
# Inject env vars before importing src — Settings() instantiates at import time
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")


@pytest.fixture(autouse=True)
def reset_bot_limiter():
    """모듈 레벨 _bot_limiter 싱글톤을 매 테스트마다 클리어 — 테스트 간 격리.
    Clear the module-level _bot_limiter singleton between tests for isolation.
    """
    from src.webhook.providers import github as gh_module
    gh_module._bot_limiter._events.clear()
    yield
    gh_module._bot_limiter._events.clear()


def _make_push_data(
    *,
    sender_type: str = "User",
    sender_login: str = "xzawed",
    commit_msg: str = "normal commit",
    repo: str = "xzawed/SCAManager",
    include_sender: bool = True,
) -> dict:
    """push 이벤트 페이로드 헬퍼 — sender 필드 포함/누락 제어 가능.
    Push event payload helper — controls inclusion/omission of the sender field.
    """
    data: dict = {
        "repository": {"full_name": repo},
        "head_commit": {"message": commit_msg},
    }
    if include_sender:
        data["sender"] = {"type": sender_type, "login": sender_login}
    return data


# ──────────────────────────────────────────────────────────────────────────
# 4 핵심 시나리오 — 정책 변경 검증 (#1, #4 는 Red 예상)
# Four core scenarios — policy change verification (#1, #4 expected Red)
# ──────────────────────────────────────────────────────────────────────────


def test_human_sender_passes_without_rate_limit():
    """사람 발신(User) 100회 push 가 모두 None 을 반환 — 파이프라인 정상 진행.
    Human sender (User) sending 100 pushes — all return None (pipeline proceeds).
    """
    from src.webhook.providers.github import _loop_guard_check

    data = _make_push_data(sender_type="User", sender_login="xzawed")
    for _ in range(100):
        result = _loop_guard_check(data)
        assert result is None, "사람 발신은 rate-limit 대상이 아니어야 한다"


def test_whitelisted_bot_blocked_after_limit():
    """화이트리스트 봇(github-actions)은 시간당 6회 통과 후 7회째에 bot_rate_limit 차단.
    Whitelisted bot (github-actions) — 6 events pass, 7th returns bot_rate_limit.
    """
    from src.webhook.providers.github import _loop_guard_check

    data = _make_push_data(
        sender_type="Bot",
        sender_login="github-actions[bot]",
    )
    # 처음 6회는 통과 (None) — Layer 2 통과 + Layer 3-b 한도 내
    # First 6 calls pass (None) — clears Layer 2 + within Layer 3-b cap
    for i in range(6):
        result = _loop_guard_check(data)
        assert result is None, f"화이트리스트 봇 {i+1}회차는 통과해야 한다"

    # 7회째는 차단 — bot_rate_limit
    # 7th call blocked — bot_rate_limit
    seventh = _loop_guard_check(data)
    assert seventh == {"status": "skipped", "reason": "bot_rate_limit"}


def test_non_whitelisted_bot_blocked_at_layer2():
    """비-화이트리스트 봇(renovate)은 첫 호출에서 Layer 2 로 즉시 bot_sender 차단.
    Non-whitelisted bot (renovate) — blocked immediately by Layer 2 (bot_sender).
    """
    from src.webhook.providers.github import _loop_guard_check

    data = _make_push_data(
        sender_type="Bot",
        sender_login="renovate[bot]",
    )
    result = _loop_guard_check(data)
    assert result == {"status": "skipped", "reason": "bot_sender"}


def test_missing_sender_passes_without_rate_limit():
    """sender 필드 자체가 없는 페이로드도 사람과 동일하게 무제한 통과.
    Payload with missing sender field — bypasses rate limit (treated as human).
    """
    from src.webhook.providers.github import _loop_guard_check

    data = _make_push_data(include_sender=False)
    assert "sender" not in data, "sender 필드가 페이로드에 없어야 한다"

    for _ in range(100):
        result = _loop_guard_check(data)
        assert result is None, "sender 누락 페이로드는 무제한 통과해야 한다"


# ──────────────────────────────────────────────────────────────────────────
# 회귀 테스트 — 기존 동작 유지 확인 (#5, #6 Green 예상)
# Regression tests — verifying existing behavior is preserved (#5, #6 expected Green)
# ──────────────────────────────────────────────────────────────────────────


def test_skip_marker_in_commit_msg_blocks():
    """사람 발신이라도 commit message 에 [skip-sca] 마커가 있으면 skip_marker 반환.
    Even human senders are blocked when commit message contains a [skip-sca] marker.
    """
    from src.webhook.providers.github import _loop_guard_check

    data = _make_push_data(
        sender_type="User",
        sender_login="xzawed",
        commit_msg="chore: routine update [skip-sca]",
    )
    result = _loop_guard_check(data)
    assert result == {"status": "skipped", "reason": "skip_marker"}


def test_kill_switch_disables_everything():
    """kill-switch 활성화 시 모든 이벤트가 self_analysis_disabled 로 즉시 차단.
    When kill-switch is enabled, every event is blocked with self_analysis_disabled.

    settings 싱글톤 직접 mutate 대신 모듈 참조를 patch — 테스트 격리 보장.
    Patch the module-level settings reference instead of mutating the singleton —
    ensures test isolation when run alongside test_router.py and others.
    """
    from src.webhook.providers.github import _loop_guard_check

    # 사람 / 화이트리스트 봇 / 비-화이트리스트 봇 / sender 누락 — 전부 차단
    # Human / whitelisted bot / non-whitelisted bot / missing sender — all blocked
    payloads = [
        _make_push_data(sender_type="User", sender_login="xzawed"),
        _make_push_data(sender_type="Bot", sender_login="github-actions[bot]"),
        _make_push_data(sender_type="Bot", sender_login="renovate[bot]"),
        _make_push_data(include_sender=False),
    ]
    with patch("src.webhook.providers.github.settings") as mock_settings:
        mock_settings.scamanager_self_analysis_disabled = True
        for data in payloads:
            result = _loop_guard_check(data)
            assert result == {"status": "skipped", "reason": "self_analysis_disabled"}
