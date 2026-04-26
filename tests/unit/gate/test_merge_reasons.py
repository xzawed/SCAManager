"""merge_reasons 신규 기능 단위 테스트 (Phase 12 T3).
Unit tests for new merge_reasons functionality (Phase 12 T3).
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import pytest

from src.gate.merge_reasons import (
    ALREADY_MERGED,
    CONFIG_CHANGED,
    DEFERRED,
    OPTIONAL_CHECK_ONLY,
    SHA_DRIFT,
    UNKNOWN_STATE_TIMEOUT,
    UNSTABLE_CI,
    is_retriable_tag,
    mergeable_state_to_reason,
)


# ---------------------------------------------------------------------------
# is_retriable_tag — 재시도 가능 태그 판별
# ---------------------------------------------------------------------------


def test_is_retriable_tag_unstable_ci_returns_true():
    # UNSTABLE_CI 는 재시도 대기 가능한 태그
    # UNSTABLE_CI is a tag the retry system can wait out
    assert is_retriable_tag(UNSTABLE_CI) is True


def test_is_retriable_tag_unknown_state_timeout_returns_true():
    # UNKNOWN_STATE_TIMEOUT 은 재시도 대기 가능한 태그
    # UNKNOWN_STATE_TIMEOUT is a tag the retry system can wait out
    assert is_retriable_tag(UNKNOWN_STATE_TIMEOUT) is True


@pytest.mark.parametrize(
    "tag",
    [
        "dirty_conflict",
        "branch_protection_blocked",
        "behind_base",
        "draft_pr",
        "permission_denied",
        "not_mergeable",
        "unprocessable",
        "conflict_sha_changed",
        "network_error",
        "unknown",
        "deferred",
        "already_merged",
        "sha_drift",
        "config_changed",
        "optional_check_only",
    ],
)
def test_is_retriable_tag_terminal_tags_return_false(tag):
    # 종결 태그(terminal tag)는 재시도 불가 — False 반환
    # Terminal tags are not retriable — must return False
    assert is_retriable_tag(tag) is False


# ---------------------------------------------------------------------------
# mergeable_state_to_reason — 새 상태값 ("has_hooks", "clean")
# ---------------------------------------------------------------------------


def test_mergeable_state_to_reason_has_hooks():
    # "has_hooks" 상태는 "has_hooks" 태그를 반환해야 함
    # "has_hooks" state should return the "has_hooks" tag
    assert mergeable_state_to_reason("has_hooks") == "has_hooks"


def test_mergeable_state_to_reason_clean():
    # "clean" 상태는 "clean" 태그를 반환해야 함 (병합 성공, 실패 아님)
    # "clean" state should return "clean" tag (merge succeeded, not a failure)
    assert mergeable_state_to_reason("clean") == "clean"


# ---------------------------------------------------------------------------
# 신규 상수 임포트 가능성 확인 (Phase 12 재시도 큐 전용 태그)
# Verify new constants are importable (Phase 12 retry queue specific tags)
# ---------------------------------------------------------------------------


def test_new_constants_are_importable_and_correct():
    # Phase 12 T3 신규 상수 5종 문자열값 검증
    # Validates the string values of the 5 new Phase 12 T3 constants
    assert DEFERRED == "deferred"
    assert ALREADY_MERGED == "already_merged"
    assert SHA_DRIFT == "sha_drift"
    assert CONFIG_CHANGED == "config_changed"
    assert OPTIONAL_CHECK_ONLY == "optional_check_only"
