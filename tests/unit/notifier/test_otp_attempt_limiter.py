"""_OtpAttemptLimiter 단위 테스트 — OTP brute-force 슬라이딩 윈도우 (C12).
Unit tests for _OtpAttemptLimiter — OTP brute-force sliding window (C12).

`time.time` 을 patch 해 윈도우 슬라이딩을 결정론적으로 검증한다.
Patches `time.time` to verify window sliding deterministically.
"""
# pylint: disable=redefined-outer-name
import os

# src 모듈 임포트 전 환경변수 주입 필수
# Inject env vars before any src.* import that triggers Settings() loading
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import patch

import pytest

from src.constants import (
    OTP_ATTEMPT_WINDOW_SECONDS,
    OTP_LIMITER_MAX_KEYS,
    OTP_MAX_FAILED_ATTEMPTS,
)
from src.notifier.telegram_commands import _OtpAttemptLimiter


@pytest.fixture()
def limiter() -> _OtpAttemptLimiter:
    """매 테스트마다 새 limiter 인스턴스 (격리)."""
    return _OtpAttemptLimiter()


def test_not_blocked_initially(limiter):
    """기록이 없으면 차단되지 않는다."""
    assert limiter.is_blocked("tg-1") is False


def test_blocks_after_max_failures(limiter):
    """윈도우 내 실패가 한도에 도달하면 차단한다."""
    for _ in range(OTP_MAX_FAILED_ATTEMPTS):
        assert limiter.is_blocked("tg-1") is False
        limiter.record_failure("tg-1")
    # 한도 도달 — 이후 차단
    # Cap reached — now blocked
    assert limiter.is_blocked("tg-1") is True


def test_clear_resets_failures(limiter):
    """clear 호출 시 실패 기록이 초기화된다 (성공 사용자 보호)."""
    for _ in range(OTP_MAX_FAILED_ATTEMPTS):
        limiter.record_failure("tg-1")
    assert limiter.is_blocked("tg-1") is True
    limiter.clear("tg-1")
    assert limiter.is_blocked("tg-1") is False


def test_per_key_isolation(limiter):
    """telegram_user_id 별로 카운터가 독립적이다."""
    for _ in range(OTP_MAX_FAILED_ATTEMPTS):
        limiter.record_failure("tg-attacker")
    assert limiter.is_blocked("tg-attacker") is True
    # 다른 사용자는 영향 없음
    # A different user is unaffected
    assert limiter.is_blocked("tg-victim") is False


def test_window_slides_after_expiry(limiter):
    """윈도우 경과 후 옛 실패는 만료되어 다시 허용된다."""
    base = 1000.0
    with patch("src.notifier.telegram_commands.time.time") as mock_time:
        mock_time.return_value = base
        for _ in range(OTP_MAX_FAILED_ATTEMPTS):
            limiter.record_failure("tg-1")
        assert limiter.is_blocked("tg-1") is True

        # 윈도우 + 1초 경과 → 만료 → 차단 해제
        # Advance past the window → entries expire → unblocked
        mock_time.return_value = base + OTP_ATTEMPT_WINDOW_SECONDS + 1
        assert limiter.is_blocked("tg-1") is False


def test_partial_window_still_blocks(limiter):
    """윈도우 일부만 경과하면 옛 실패가 여전히 유효해 차단 유지."""
    base = 2000.0
    with patch("src.notifier.telegram_commands.time.time") as mock_time:
        mock_time.return_value = base
        for _ in range(OTP_MAX_FAILED_ATTEMPTS):
            limiter.record_failure("tg-1")
        # 윈도우 절반만 경과 → 여전히 차단
        # Only half the window elapsed → still blocked
        mock_time.return_value = base + OTP_ATTEMPT_WINDOW_SECONDS / 2
        assert limiter.is_blocked("tg-1") is True


def test_key_dict_bounded(limiter):
    """추적 키 수가 상한(OTP_LIMITER_MAX_KEYS)을 초과해 무한 증가하지 않는다."""
    base = 5000.0
    with patch("src.notifier.telegram_commands.time.time") as mock_time:
        mock_time.return_value = base
        # 상한 + 여유분 만큼 만료된 키를 생성
        # Create more keys than the cap, all in an expired window
        for i in range(OTP_LIMITER_MAX_KEYS + 50):
            limiter.record_failure(f"tg-{i}")
        # 새 키 추가 시 만료/정리되어 상한 이내 유지
        # On insert, stale eviction keeps the dict within the cap
        mock_time.return_value = base + OTP_ATTEMPT_WINDOW_SECONDS + 1
        limiter.record_failure("tg-fresh")
        assert len(limiter._failures) <= OTP_LIMITER_MAX_KEYS
