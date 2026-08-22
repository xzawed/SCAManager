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
# should_retry — reason_tag × ci_status matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reason_tag,ci_status,expected",
    [
        ("unstable_ci", "running", True),
        ("unstable_ci", "passed", True),
        ("unstable_ci", "failed", False),
        ("unstable_ci", "unknown", True),
        ("unknown_state_timeout", "running", True),
        ("unknown_state_timeout", "passed", False),
        ("unknown_state_timeout", "failed", False),
        ("unknown_state_timeout", "unknown", False),
        ("dirty_conflict", "running", False),
        # 🔴 R68 계약 변경 — `blocked` 은 required check 진행 중일 **때만** 재시도한다.
        #    CI 가 끝났는데도 blocked = 규칙상 충족 불가 → 종결(예산 낭비 방지).
        ("branch_protection_blocked", "running", True),
        ("branch_protection_blocked", "passed", False),
        ("branch_protection_blocked", "failed", False),
        ("branch_protection_blocked", "unknown", False),
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


def test_retriable_tags_parity_with_should_retry():
    """_RETRIABLE_TAGS 의 모든 태그는 should_retry 에서 최소 1개 ci_status 로 True 를 내야 한다.
    Every tag in _RETRIABLE_TAGS must yield True from should_retry for at least one ci_status.

    드리프트 가드: retriable 멤버십 단일 출처(merge_reasons._RETRIABLE_TAGS)에 새 태그를 추가하면서
    retry_policy.should_retry 의 타이밍 분기를 빠뜨리면, is_retriable_tag 는 통과하지만 should_retry 가
    어떤 ci_status 로도 True 를 못 내 silent 미재시도(즉시 터미널)가 발생한다. 본 테스트가 그 누락을 차단.
    Drift guard: adding a tag to the single-source _RETRIABLE_TAGS without a matching timing branch in
    should_retry would let is_retriable_tag pass yet should_retry never return True → silent no-retry.
    """
    from src.gate.merge_reasons import _RETRIABLE_TAGS

    ci_statuses = ("running", "passed", "failed", "unknown")
    for tag in _RETRIABLE_TAGS:
        assert any(should_retry(tag, ci) for ci in ci_statuses), (
            f"'{tag}' 가 _RETRIABLE_TAGS 에 있으나 should_retry 가 어떤 ci_status 로도 True 를 내지 못함 "
            f"— retry_policy.should_retry 에 타이밍 분기 추가 필요 (단일출처 drift)"
        )


def test_unstable_ci_passed_retry_is_intentional_lag_tolerance():
    """UNSTABLE_CI + ci_status='passed' 재시도는 의도적 설계 — 무심코 terminal 전환 회귀 차단 (#23).

    정합성 감사 #23 은 'passed' 재시도를 '영구 재시도'로 표현했으나 부정확 — 재시도 예산은
    is_expired(max_age, 기본 24h)와 재시도 서비스의 max_attempts cap(기본 30 → abandoned)으로 bounded
    (is_expired 자체는 max_age 만 검사; test_is_expired_* 가드). 'passed' 분기 =
    CI 통과했으나 mergeable_state 미반영(merge API lag) 또는 일부 check suite pending 시 재시도를
    위한 수용된 트레이드오프 (사용자 결정 A — 현 설계 유지). 본 가드는 향후 'passed'→terminal 회귀를
    차단한다(정상 lag 케이스 false terminal 방지).

    'passed' retry is intentional (merge-API lag tolerance) — this guard blocks a regression that
    would make it terminal. Budget is bounded by is_expired (24h / 30 attempts), not infinite.
    """
    assert should_retry("unstable_ci", "passed") is True
    # 동일 분기의 running/unknown 도 의도적 재시도 (lag/transient 보호)
    # running/unknown in the same branch are also intentional retries (lag / transient protection)
    assert should_retry("unstable_ci", "running") is True
    assert should_retry("unstable_ci", "unknown") is True
    # 'failed' 는 재시도 아님 (실제 CI 실패)
    # 'failed' is not retried (genuine CI failure)
    assert should_retry("unstable_ci", "failed") is False


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


# ─── 🔴 만료 판정은 **순간**에 달려야 한다 — 그 순간을 어느 시간대로 표현했든 ────────
#
# 위 `test_is_expired_*` 는 전부 `now` 를 UTC 로 넘긴다. 그래서 `is_expired` 가 tzinfo 를
# **변환 없이 벗기는** 것(`now.replace(tzinfo=None)`)이 드러나지 않았다. UTC 를 벗기면
# 우연히 맞는 값이 나오기 때문이다.
#
# 이 저장소는 이 클래스를 이미 한 번 겪었다 — `src/shared/time_utils.py` 머리말:
# "#1197 이 3곳만 고쳐(정책 16 grep 전수 위반) 회고 P1-B 로 재적발됨". 그래서 만들어 둔
# 것이 `to_naive_utc`(먼저 UTC 로 변환하고 벗긴다)인데, 정작 이 함수가 그것을 쓰지 않았다.
#
# Every existing test passes a UTC `now`, so stripping tzinfo without converting looks correct.
# The verdict must depend on the instant, not on how the caller spelled it.

def _same_instant_in(offset_hours: int, utc_dt: datetime) -> datetime:
    """같은 순간을 다른 UTC 오프셋으로 표현한 값."""
    return utc_dt.astimezone(timezone(timedelta(hours=offset_hours)))


def test_is_expired_is_independent_of_the_callers_timezone():
    """같은 순간이면 표현 시간대와 무관하게 같은 판정이어야 한다.

    🔴 실패 시 무엇이 깨지는가: `now` 가 KST(+9)로 들어오면 만료가 **9시간 일찍** 선언된다.
    재시도 큐 행이 아직 유효한데 expired 로 종결돼 **PR 이 자동 머지되지 않는다**.
    반대 부호(-05:00)면 만료가 늦게 와서 `max_age` 상한이 사실상 느슨해진다 —
    무한 재시도를 막으려고 둔 두 상한 중 하나가 거짓이 된다.
    """
    now_utc = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 4, 25, 13, 0, 0)  # 23시간 전 (naive UTC) → 아직 유효
    row = _FakeRow(created_at=created)

    baseline = is_expired(row, now=now_utc)
    assert baseline is False, "기준 케이스 자체가 틀렸다 — 픽스처 점검 필요"

    for offset in (9, 5, -5, -8):
        shifted = _same_instant_in(offset, now_utc)
        assert shifted == now_utc, "같은 순간이 아니다 — 테스트 구성 오류"
        assert is_expired(row, now=shifted) is baseline, (
            f"UTC{offset:+d} 로 표현했더니 판정이 뒤집혔다 — tzinfo 를 변환 없이 벗기고 있다. "
            f"`to_naive_utc(now)` 를 경유할 것 (src/shared/time_utils.py)."
        )


def test_is_expired_is_independent_of_timezone_on_the_expired_side():
    """대조축 — 만료된 행에서도 같아야 한다. 한쪽 방향만 보면 절반만 고쳐도 통과한다."""
    now_utc = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    created = datetime(2026, 4, 25, 11, 0, 0)  # 25시간 전 → 만료
    row = _FakeRow(created_at=created)

    assert is_expired(row, now=now_utc) is True, "기준 케이스 점검 필요"
    for offset in (9, -8):
        assert is_expired(row, now=_same_instant_in(offset, now_utc)) is True, (
            f"UTC{offset:+d} 에서 만료된 행이 유효로 판정됐다 — 재시도가 상한 없이 계속된다"
        )


def test_naive_now_still_works_unchanged():
    """회귀 방지 — naive `now` 는 그대로 통과해야 한다(`to_naive_utc` 의 통과 분기)."""
    created = datetime(2026, 4, 25, 11, 0, 0)
    row = _FakeRow(created_at=created)
    assert is_expired(row, now=datetime(2026, 4, 26, 12, 0, 0)) is True
