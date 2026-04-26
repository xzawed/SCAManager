"""Auto-merge 실패 사유 정규 태그 — Phase F 관측 + 알림 고도화 공용 상수.

기존 `github_review.py::_interpret_merge_error` 가 반환하던 문자열 라벨을
모듈 상수로 승격. Phase F.1 의 `MergeAttempt.failure_reason` enum 과 동일한
네이밍을 사용하도록 조율 — 하나의 정규 태그 체계로 전체 파이프라인 일관화.

사용처:
  - `src/gate/github_review.py::merge_pr` — mergeable_state / HTTP 에러 분류
  - `src/gate/engine.py::_run_auto_merge` — Telegram 알림 + (F.1) DB 기록
  - `src/gate/merge_failure_advisor.py` (F.3) — 권장 조치 매핑
  - `src/gate/retry_policy.py` (Phase 12) — 재시도 큐 태그 판별
"""

# --- mergeable_state 사전 차단 사유 -----------------------------------------
BRANCH_PROTECTION_BLOCKED = "branch_protection_blocked"  # state=blocked
DIRTY_CONFLICT = "dirty_conflict"                        # state=dirty
BEHIND_BASE = "behind_base"                              # state=behind
DRAFT_PR = "draft_pr"                                    # state=draft
UNSTABLE_CI = "unstable_ci"                              # state=unstable (P0, Phase F QW1)
UNKNOWN_STATE_TIMEOUT = "unknown_state_timeout"          # state=unknown after retries

# --- HTTP 오류 분류 ---------------------------------------------------------
PERMISSION_DENIED = "permission_denied"   # HTTP 403
NOT_MERGEABLE = "not_mergeable"           # HTTP 405
UNPROCESSABLE = "unprocessable"           # HTTP 422
CONFLICT_SHA_CHANGED = "conflict_sha_changed"  # HTTP 409

# --- 네트워크 / 기타 --------------------------------------------------------
# --- Network / other --------------------------------------------------------
NETWORK_ERROR = "network_error"           # httpx.HTTPError (non-status)
UNKNOWN = "unknown"                       # 분류 불가

# --- Phase 12 재시도 큐 전용 태그 -------------------------------------------
# --- Phase 12 retry queue specific tags -------------------------------------
DEFERRED = "deferred"                     # 재시도 대기 중 (첫 번째 지연 항목)
                                          # Waiting for retry (initial deferral entry)
ALREADY_MERGED = "already_merged"         # 이미 병합됨 (중복 감지)
                                          # Already merged (duplicate detection)
SHA_DRIFT = "sha_drift"                   # force-push 로 커밋 SHA 변경됨
                                          # Commit SHA changed due to force-push
CONFIG_CHANGED = "config_changed"         # 사용자가 설정 변경 (auto_merge 해제 등)
                                          # User changed config (auto_merge disabled etc.)
OPTIONAL_CHECK_ONLY = "optional_check_only"  # 실패 체크가 선택적(optional)만 포함
                                             # Only optional checks are failing

# 재시도 시스템이 대기할 수 있는 태그 집합 (is_retriable_tag 단일 출처)
# Tag set the retry system can wait out (single source for is_retriable_tag)
_RETRIABLE_TAGS: frozenset[str] = frozenset({UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT})


# HTTP 상태 코드 → reason tag 매핑 (`_interpret_merge_error` 용)
_HTTP_STATUS_TO_REASON: dict[int, str] = {
    403: PERMISSION_DENIED,
    405: NOT_MERGEABLE,
    409: CONFLICT_SHA_CHANGED,
    422: UNPROCESSABLE,
}


def http_status_to_reason(code: int) -> str:
    """HTTP 상태 코드를 정규 reason tag 로 변환. 미지의 코드는 `http_{code}` 형식."""
    return _HTTP_STATUS_TO_REASON.get(code, f"http_{code}")


# mergeable_state → reason tag 매핑
# "unknown" 은 포함하지 않음 — mergeable_state_to_reason 이 UNKNOWN 태그로 처리
# "unknown" is not included — mergeable_state_to_reason handles it as UNKNOWN tag
_MERGEABLE_STATE_TO_REASON: dict[str, str] = {
    "dirty": DIRTY_CONFLICT,
    "blocked": BRANCH_PROTECTION_BLOCKED,
    "behind": BEHIND_BASE,
    "draft": DRAFT_PR,
    "unstable": UNSTABLE_CI,
    "has_hooks": "has_hooks",  # 훅 검사 중 — 대기 상태
                               # Awaiting hook checks — transient hold state
    "clean": "clean",          # 병합 가능 — 실패 아님
                               # Mergeable — not a failure state
}


def mergeable_state_to_reason(state: str) -> str:
    """mergeable_state 문자열 → 정규 reason tag.
    Convert mergeable_state string to a canonical reason tag.
    """
    return _MERGEABLE_STATE_TO_REASON.get(state, UNKNOWN)


def is_retriable_tag(tag: str) -> bool:
    """재시도 시스템이 대기할 수 있는 태그인지 확인.
    Check if the tag is one the retry system can wait out.

    재시도 가능: UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT
    Retriable:  UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT

    그 외 모든 태그는 종결(terminal) 태그로 재시도 불가.
    All other tags are terminal and not retriable.
    """
    return tag in _RETRIABLE_TAGS
