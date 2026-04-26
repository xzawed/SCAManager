"""retry_policy 순수 함수 단위 테스트.
Unit tests for retry_policy pure functions.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from datetime import datetime, timedelta, timezone

import pytest

from src.gate.retry_policy import (
    compute_next_retry_at,
    is_expired,
    mergeable_state_terminality,
    parse_reason_tag,
    should_retry,
)


# ---------------------------------------------------------------------------
# parse_reason_tag
# ---------------------------------------------------------------------------


def test_parse_reason_tag_with_colon_suffix():
    # 콜론 이후 세부 내용이 있을 때 기본 태그만 반환
    # Returns only the base tag when detail follows a colon
    result = parse_reason_tag("unstable_ci: state=unstable, merged=False")
    assert result == "unstable_ci"


def test_parse_reason_tag_without_colon():
    # 콜론 없이 단순 태그 문자열이면 그대로 반환
    # Returns the string as-is when there is no colon
    result = parse_reason_tag("dirty_conflict")
    assert result == "dirty_conflict"


def test_parse_reason_tag_none_returns_unknown():
    # None 입력 시 'unknown' 반환
    # Returns 'unknown' when input is None
    assert parse_reason_tag(None) == "unknown"


def test_parse_reason_tag_empty_returns_unknown():
    # 빈 문자열 입력 시 'unknown' 반환
    # Returns 'unknown' when input is an empty string
    assert parse_reason_tag("") == "unknown"


def test_parse_reason_tag_whitespace_stripped():
    # 콜론 앞의 공백이 제거된 태그 반환
    # Returns tag with surrounding whitespace stripped
    result = parse_reason_tag("  branch_protection_blocked  : details here")
    assert result == "branch_protection_blocked"


# ---------------------------------------------------------------------------
# mergeable_state_terminality — 8-state matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "state,expected",
    [
        ("clean", "terminal"),
        ("unstable", "needs_disambiguation"),
        ("unknown", "retriable"),
        ("blocked", "terminal"),
        ("behind", "terminal"),
        ("dirty", "terminal"),
        ("draft", "terminal"),
        ("has_hooks", "terminal"),
        ("totally_made_up_state", "terminal"),
    ],
)
def test_mergeable_state_terminality_matrix(state, expected):
    # 8가지 GitHub mergeable_state 값 + 미지 상태 반환값 검증
    # Validates return value for the 8 known GitHub mergeable_state values plus unknown
    assert mergeable_state_terminality(state) == expected


# ---------------------------------------------------------------------------
# should_retry — reason_tag × ci_status matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason_tag,ci_status,expected",
    [
        ("unstable_ci", "running", True),
        ("unstable_ci", "passed", True),
        ("unstable_ci", "failed", False),
        ("unstable_ci", "unknown", False),
        ("unknown_state_timeout", "running", True),
        ("unknown_state_timeout", "passed", False),
        ("unknown_state_timeout", "failed", False),
        ("unknown_state_timeout", "unknown", False),
        ("dirty_conflict", "running", False),
        ("branch_protection_blocked", "running", False),
        ("behind_base", "passed", False),
        ("permission_denied", "running", False),
        ("network_error", "running", False),
        ("unknown", "running", False),
    ],
)
def test_should_retry_matrix(reason_tag, ci_status, expected):
    # reason_tag 와 ci_status 조합별 재시도 결정값 검증
    # Validates the retry decision for each reason_tag × ci_status combination
    assert should_retry(reason_tag, ci_status) is expected


# ---------------------------------------------------------------------------
# compute_next_retry_at
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


def test_compute_next_retry_at_initial_backoff():
    # attempts=0 일 때 기본 백오프(60초) 기반으로 다음 재시도 시각 계산
    # Computes next retry using initial backoff (60s) when attempts_count=0
    result = compute_next_retry_at(0, now=_NOW)
    base = 60
    lower = _NOW + timedelta(seconds=base * 0.75)
    upper = _NOW + timedelta(seconds=base * 1.25 + 1)
    assert lower <= result <= upper


def test_compute_next_retry_at_second_attempt():
    # attempts=1 일 때 백오프 2배(120초) 기반으로 계산
    # Computes next retry using doubled backoff (120s) when attempts_count=1
    result = compute_next_retry_at(1, now=_NOW)
    base = 120
    lower = _NOW + timedelta(seconds=base * 0.75)
    upper = _NOW + timedelta(seconds=base * 1.25 + 1)
    assert lower <= result <= upper


def test_compute_next_retry_at_caps_at_max_backoff():
    # 시도 횟수가 매우 클 때 max_backoff(600초)로 cap
    # Caps at max_backoff (600s) when attempts_count is very large
    result = compute_next_retry_at(99, now=_NOW)
    max_backoff = 600
    lower = _NOW + timedelta(seconds=max_backoff * 0.75)
    upper = _NOW + timedelta(seconds=max_backoff * 1.25 + 1)
    assert lower <= result <= upper


def test_compute_next_retry_at_custom_backoff():
    # 커스텀 initial_backoff / max_backoff 파라미터 적용 확인
    # Validates custom initial_backoff and max_backoff parameters are applied
    result = compute_next_retry_at(0, now=_NOW, initial_backoff=30, max_backoff=300)
    base = 30
    lower = _NOW + timedelta(seconds=base * 0.75)
    upper = _NOW + timedelta(seconds=base * 1.25 + 1)
    assert lower <= result <= upper


def test_compute_next_retry_at_jitter_within_bounds():
    # 100회 반복 시 모든 결과가 ±25% 지터 범위 내에 있어야 함
    # All 100 results must fall within ±25% jitter bounds over 100 runs
    base = 60  # attempts=0 → initial_backoff * 2**0 = 60
    lower = _NOW + timedelta(seconds=base * 0.75)
    upper = _NOW + timedelta(seconds=base * 1.25 + 1)
    for _ in range(100):
        result = compute_next_retry_at(0, now=_NOW)
        assert lower <= result <= upper, f"Jitter out of bounds: {result}"


def test_compute_next_retry_at_always_at_least_one_second():
    # 결과는 항상 now보다 최소 1초 이상 미래여야 함
    # Result must always be at least 1 second after 'now'
    for _ in range(20):
        result = compute_next_retry_at(0, now=_NOW)
        assert result >= _NOW + timedelta(seconds=1)


def test_compute_next_retry_at_result_is_future():
    # 계산 결과가 항상 now 이후여야 함
    # Result must always be strictly after now
    result = compute_next_retry_at(0, now=_NOW)
    assert result > _NOW


# ---------------------------------------------------------------------------
# is_expired
# ---------------------------------------------------------------------------


class _FakeRow:
    """ORM Row 덕 타이핑용 가짜 객체 — created_at 속성만 보유.
    Fake object for duck-typing the ORM row — only has a created_at attribute.
    """

    def __init__(self, created_at: datetime) -> None:
        self.created_at = created_at


def test_is_expired_when_within_limit():
    # 생성 후 23시간 경과: 아직 만료되지 않음
    # 23 hours elapsed since creation: not yet expired
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 4, 25, 13, 0, 0)  # 23 hours ago (naive)
    row = _FakeRow(created_at=created)
    assert is_expired(row, now=now) is False


def test_is_expired_when_past_limit():
    # 생성 후 25시간 경과: 만료됨
    # 25 hours elapsed since creation: expired
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 4, 25, 11, 0, 0)  # 25 hours ago (naive)
    row = _FakeRow(created_at=created)
    assert is_expired(row, now=now) is True


def test_is_expired_exactly_at_boundary():
    # 정확히 24시간 경과: 만료로 처리 (초과가 아닌 경계값)
    # Exactly 24 hours elapsed: treated as expired (boundary, not strictly over)
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 4, 25, 12, 0, 0)  # exactly 24 hours ago (naive)
    row = _FakeRow(created_at=created)
    assert is_expired(row, now=now) is True


def test_is_expired_custom_max_age():
    # 커스텀 max_age_hours=1 설정: 2시간 경과면 만료
    # Custom max_age_hours=1: expired when 2 hours have elapsed
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 4, 26, 10, 0, 0)  # 2 hours ago (naive)
    row = _FakeRow(created_at=created)
    assert is_expired(row, now=now, max_age_hours=1) is True


def test_is_expired_custom_max_age_within_limit():
    # 커스텀 max_age_hours=3 설정: 2시간 경과면 아직 유효
    # Custom max_age_hours=3: still valid when only 2 hours have elapsed
    now = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 4, 26, 10, 0, 0)  # 2 hours ago (naive)
    row = _FakeRow(created_at=created)
    assert is_expired(row, now=now, max_age_hours=3) is False
