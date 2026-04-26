"""Auto-merge 재시도 정책 순수 함수 모음 — Phase 12 T2.
Pure functions for auto-merge retry policy — Phase 12 T2.

DB / HTTP 의존 없음 — 단위 테스트 고속 실행 가능.
No DB / HTTP dependencies — enables fast unit testing.
"""
import random
from datetime import datetime, timedelta

from src.gate.merge_reasons import UNKNOWN_STATE_TIMEOUT, UNSTABLE_CI


def parse_reason_tag(reason: str | None) -> str:
    """reason 문자열에서 기본 태그 추출 (콜론 이전 부분).
    Extract the base tag from a reason string (part before the colon).

    Examples:
        "unstable_ci: state=unstable, merged=False" → "unstable_ci"
        "dirty_conflict" → "dirty_conflict"
        None → "unknown"
        "" → "unknown"
    """
    # None 또는 빈 문자열이면 'unknown' 반환
    # Return 'unknown' for None or empty string
    if not reason:
        return "unknown"

    # 콜론 앞 부분만 추출하고 공백 제거
    # Extract the part before the colon and strip surrounding whitespace
    return reason.split(":")[0].strip() or "unknown"


# mergeable_state → terminality 매핑 상수 (순수 데이터)
# Constant mapping of mergeable_state → terminality (pure data)
_STATE_TERMINALITY: dict[str, str] = {
    # GitHub가 여전히 계산 중 — 잠시 대기 후 재시도
    # GitHub is still computing — wait briefly and retry
    "unknown": "retriable",
    # CI 진행 중일 수도, 실패했을 수도 있음 — 추가 판단 필요
    # Could be CI running or a failing check — needs further disambiguation
    "unstable": "needs_disambiguation",
    # 이하 모두 즉시 종료 (재시도 불가)
    # All states below are immediately terminal (no retry)
    "clean": "terminal",
    "blocked": "terminal",
    "behind": "terminal",
    "dirty": "terminal",
    "draft": "terminal",
    "has_hooks": "terminal",
}


def mergeable_state_terminality(state: str) -> str:
    """mergeable_state → 'retriable'|'terminal'|'needs_disambiguation'.

    Args:
        state: GitHub PR mergeable_state 문자열.
               GitHub PR mergeable_state string.

    Returns:
        'retriable'            — 잠시 후 재시도 가능 / can retry shortly
        'terminal'             — 재시도해도 결과 변화 없음 / no point retrying
        'needs_disambiguation' — CI 상태 추가 조회 필요 / needs CI status check
    """
    # 알 수 없는 상태는 terminal 로 안전하게 처리
    # Unknown states default to terminal for safety
    return _STATE_TERMINALITY.get(state, "terminal")


def should_retry(reason_tag: str, ci_status: str) -> bool:
    """재시도 여부 결정 — reason_tag 와 ci_status 조합으로 판단.
    Determines whether to retry based on reason_tag and ci_status combination.

    Args:
        reason_tag: 정규화된 실패 사유 태그 (parse_reason_tag 결과).
                    Normalized failure reason tag (output of parse_reason_tag).
        ci_status:  CI 현재 상태 — 'running'|'passed'|'failed'|'unknown'.
                    Current CI status — 'running'|'passed'|'failed'|'unknown'.

    Returns:
        True이면 재시도 큐에 추가, False이면 최종 실패 처리.
        True to enqueue for retry, False to treat as terminal failure.
    """
    if reason_tag == UNSTABLE_CI:
        # CI 진행 중이거나 방금 통과했으면 재시도 — merge API 갱신 지연 가능
        # Retry when CI is still running or just passed — merge API may lag
        return ci_status in ("running", "passed")

    if reason_tag == UNKNOWN_STATE_TIMEOUT:
        # GitHub가 아직 상태 계산 중일 때만 재시도
        # Retry only while GitHub is still computing its state
        return ci_status == "running"

    # 충돌·차단·뒤처짐·draft 등 재시도해도 해결 안 됨
    # Conflict / blocked / behind / draft — retrying won't help
    return False


def compute_next_retry_at(
    attempts_count: int,
    *,
    now: datetime,
    initial_backoff: int = 60,
    max_backoff: int = 600,
) -> datetime:
    """지수 백오프 + 지터로 다음 재시도 시각 계산.
    Compute next retry time using exponential backoff with jitter.

    Args:
        attempts_count:  지금까지 시도한 횟수 (0 = 첫 번째 재시도 예약).
                         Number of attempts so far (0 = scheduling first retry).
        now:             현재 시각 (timezone-aware 권장).
                         Current time (timezone-aware recommended).
        initial_backoff: 첫 번째 재시도 기본 대기 시간(초). 기본값 60.
                         Base wait time for the first retry in seconds. Default 60.
        max_backoff:     최대 대기 시간(초). 기본값 600.
                         Maximum wait time in seconds. Default 600.

    Returns:
        다음 재시도를 예약할 datetime (now 기준 최소 1초 이상 미래).
        Datetime for the next retry (at least 1 second after now).

    Formula:
        base   = min(initial_backoff * 2**attempts_count, max_backoff)
        jitter = uniform(-0.25 * base, +0.25 * base)
        delay  = max(base + jitter, 1)
    """
    # 지수 백오프 기본값 계산 (max_backoff 으로 상한)
    # Compute exponential base with max_backoff cap
    base = min(initial_backoff * (2 ** attempts_count), max_backoff)

    # ±25% 균등 분포 지터 적용 — 동시 재시도 충돌 방지 (thundering-herd 완화)
    # Apply ±25% uniform jitter — prevents thundering-herd on simultaneous retries
    jitter = random.uniform(-0.25 * base, 0.25 * base)

    # 최소 1초 보장 — 극단적 지터 시 음수 방지
    # Guarantee at least 1 second — prevents non-positive delay under extreme jitter
    delay = max(base + jitter, 1)

    return now + timedelta(seconds=delay)


def is_expired(row, *, now: datetime, max_age_hours: int = 24) -> bool:
    """재시도 큐 행이 만료되었는지 확인 (created_at 기준 max_age_hours 초과).
    Check if a retry queue row has expired (created_at + max_age_hours <= now).

    Args:
        row:           .created_at 속성을 가진 임의 객체 (ORM duck typing).
                       Any object with a .created_at attribute (ORM duck typing).
        now:           현재 시각 (timezone-aware).
                       Current time (timezone-aware).
        max_age_hours: 허용 최대 경과 시간(시간 단위). 기본값 24.
                       Maximum allowed age in hours. Default 24.

    Returns:
        True  — 만료됨 (max_age_hours 경과 또는 정확히 도달)
                Expired (max_age_hours have passed or exactly reached)
        False — 아직 유효함
                Still valid

    Note:
        ORM의 created_at 은 timezone-naive (UTC 저장 관례).
        now 는 timezone-aware 로 전달되므로 비교 전 naive 로 변환.
        The ORM created_at is timezone-naive (stored as UTC by convention).
        'now' is passed as timezone-aware, so we strip tzinfo before comparing.
    """
    # timezone-aware now를 naive UTC로 변환 후 비교
    # Convert timezone-aware now to naive UTC for comparison with naive created_at
    now_naive = now.replace(tzinfo=None)
    expiry = row.created_at + timedelta(hours=max_age_hours)
    return now_naive >= expiry
