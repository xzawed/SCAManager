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
NETWORK_ERROR = "network_error"           # HTTPX_SEND_ERRORS (전송 오류, non-status)
UNKNOWN = "unknown"                       # 분류 불가

# --- 2nd-LLM 머지 검증자 (cross-vendor 거버넌스 가드) ---------------------
# --- 2nd-LLM merge verifier (cross-vendor governance guard) ---------------
# 검증자가 머지 불안전/조작 의심 판정 → 자동머지 차단 (터미널, 재시도 불가)
# Verifier judged merge unsafe / manipulation suspected → auto-merge blocked (terminal, not retriable)
VERIFIER_BLOCKED = "verifier_blocked"
# 검증자 자체 실패(API/파싱) → fail-closed 차단 (터미널)
# Verifier itself failed (API/parse error) → fail-closed block (terminal)
VERIFIER_ERROR = "verifier_error"

# --- Phase 12 재시도 큐 전용 태그 -------------------------------------------
# --- Phase 12 retry queue specific tags -------------------------------------
# 재시도 대기 중 (첫 번째 지연 항목) / Waiting for retry (initial deferral entry)
DEFERRED = "deferred"
# 이미 병합됨 (중복 감지) / Already merged (duplicate detection)
ALREADY_MERGED = "already_merged"
# force-push 로 커밋 SHA 변경됨 / Commit SHA changed due to force-push
SHA_DRIFT = "sha_drift"

# 민감 경로(인증·마이그레이션·CI 워크플로) 포함 → 사람 검토 전까지 자동 머지 보류 (B6-a).
# Sensitive paths present → hold auto-merge until a human reviews (B6-a).
# 🔴 재시도 불가 태그다 — 기다린다고 사람이 검토하지는 않는다. 보류는 종결이지 지연이 아니다.
SENSITIVE_PATH_HOLD = "sensitive_path_hold"
# 사용자가 설정 변경 (auto_merge 해제 등) / User changed config (auto_merge disabled etc.)
CONFIG_CHANGED = "config_changed"

# 재시도 시스템이 대기할 수 있는 태그 집합 (is_retriable_tag 단일 출처)
# Tag set the retry system can wait out (single source for is_retriable_tag)
#
# 🔴 `BRANCH_PROTECTION_BLOCKED` 추가 (2026-08-08, backlog R68 · 사용자 결정).
#
# `mergeable_state="blocked"` 는 **두 가지**를 뭉뚱그린다:
#   (a) required check 가 아직 **도는 중** — 몇 분 뒤면 풀린다
#   (b) 규칙상 충족 불가(리뷰 미승인 등) — 기다려도 안 풀린다
# GitHub 은 둘을 구별해 주지 않는다. 이전에는 이 태그를 통째로 **종결**로 처리해,
# 분석이 끝난 시점에 required check 가 아직 돌고 있으면 그 PR 이 **재시도 없이 영구 포기**됐다.
#
# 이 리포는 required check **10종**(+`enforce_admins`)을 쓰고 그중 pytest·e2e 는 수 분이
# 걸리므로 (a)가 일상적으로 발생한다. `sensitive_paths.py` 가 이미 이 성질을 실측으로
# 기록해 뒀다 — *"오히려 자동 머지를 죽인다"*.
#
# 🔴 **무조건 재시도가 아니다.** 여기서는 '대기 가능' 으로만 올리고, 실제 판정은
# `retry_policy.should_retry(tag, ci_status)` 가 **CI 가 도는 중일 때만** 재시도로 확정한다.
# (b)는 CI 가 이미 끝난 상태이므로 그 분기에서 종결로 떨어진다 — 영구 차단 PR 이
# 재시도 예산을 소모하지 않는다.
#
# `blocked` conflates "required checks still running" with "rule cannot be satisfied".
# Treat it as waitable here; `should_retry` confirms only while CI is actually running.
_RETRIABLE_TAGS: frozenset[str] = frozenset(
    {UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT, BRANCH_PROTECTION_BLOCKED}
)


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


# mergeable_state → reason tag 매핑 — 차단 상태(_MERGEABLE_BLOCK)만 등재.
# 🔴 호출처(github_review.py:152)는 `if state in _MERGEABLE_BLOCK`(dirty/blocked/behind/draft/unstable)
# 가드 내부에서만 호출되므로 그 5종만 조회된다. non-block 상태(has_hooks/clean 등)는 lookup 도달 불가라
# 등재하지 않는다(도달 불가 데이터=오인 소지, 정합성 감사 C24 제거). 미지 상태는 .get(state, UNKNOWN).
# Only the blocking states (_MERGEABLE_BLOCK) are mapped — the sole caller (github_review.py:152) runs
# inside `if state in _MERGEABLE_BLOCK`, so non-block states (has_hooks/clean) can never be looked up;
# unreachable entries were removed (audit C24). Unknown states fall through to .get(state, UNKNOWN).
_MERGEABLE_STATE_TO_REASON: dict[str, str] = {
    "dirty": DIRTY_CONFLICT,
    "blocked": BRANCH_PROTECTION_BLOCKED,
    "behind": BEHIND_BASE,
    "draft": DRAFT_PR,
    "unstable": UNSTABLE_CI,
}


def mergeable_state_to_reason(state: str) -> str:
    """mergeable_state 문자열 → 정규 reason tag.
    Convert mergeable_state string to a canonical reason tag.
    """
    return _MERGEABLE_STATE_TO_REASON.get(state, UNKNOWN)


def is_retriable_tag(tag: str) -> bool:
    """재시도 시스템이 대기할 수 있는 태그인지 확인.
    Check if the tag is one the retry system can wait out.

    🔴 어떤 태그가 재시도 가능인지는 **여기에 적지 않는다** — 위의 `_RETRIABLE_TAGS`
    정의가 정본이고, 그 옆 주석이 각 태그가 거기 있는 근거를 갖는다. 여기에 옮겨
    적으면 집합이 바뀔 때 이 문장만 남아 거짓이 된다.

    🔴 「대기 가능」은 「재시도한다」가 아니다. 실제 판정은 타이밍까지 보는
    `retry_policy.should_retry(tag, ci_status)` 가 확정한다.

    The membership list lives in `_RETRIABLE_TAGS` above, not here; `should_retry` makes
    the actual call.
    """
    return tag in _RETRIABLE_TAGS
