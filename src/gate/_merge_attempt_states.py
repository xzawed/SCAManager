"""MergeAttempt.state 정규 상수 + 전이표 (Phase 3 PR-B1).

Tier 3 PR-A 후속 — native enable 성공 시 즉시 success=True 로 기록되는
관측 갭 해소. state 컬럼으로 lifecycle 추적.

MergeAttempt.state canonical constants + transition table (Phase 3 PR-B1).
Closes the observability gap from Tier 3 PR-A where native-enable success
was recorded as success=True without tracking actual merge completion.
"""
from __future__ import annotations

# 정규 state 값 — `merge_attempt_repo` 의 mark_* 함수와 일치해야 함
# Canonical state values — must match `merge_attempt_repo` mark_* functions

#: 0022 마이그레이션 이전 모든 행의 backfill 기본값. 갱신 금지.
#: Backfill default for all pre-0022 rows. Read-only.
LEGACY = "legacy"

#: native `enablePullRequestAutoMerge` mutation 성공 직후 — GitHub 가 비동기 머지 대기.
#: Right after a successful native enable mutation; GitHub will merge asynchronously.
ENABLED_PENDING_MERGE = "enabled_pending_merge"

#: `pull_request.closed merged=true` webhook 수신 → enabled_pending_merge 에서 전이.
#: After receiving a `pull_request.closed merged=true` webhook (transitions from enabled_pending_merge).
ACTUALLY_MERGED = "actually_merged"

#: `pull_request.auto_merge_disabled` webhook 수신 (force-push, check fail, 수동 해제 등).
#: After a `pull_request.auto_merge_disabled` webhook (force-push, check failure, manual disable).
DISABLED_EXTERNALLY = "disabled_externally"

#: REST `merge_pr()` 즉시 성공 — fallback 또는 legacy `_run_auto_merge_legacy` 경로.
#: REST `merge_pr()` immediate success — fallback or legacy path.
DIRECT_MERGED = "direct_merged"


# 허용된 전이만 정의 — 그 외 전이는 idempotent no-op (mark_* 함수에서 WHERE 절로 강제)
# Allowed transitions only — others are idempotent no-ops (enforced via mark_* WHERE clauses)
ALLOWED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    (ENABLED_PENDING_MERGE, ACTUALLY_MERGED),
    (ENABLED_PENDING_MERGE, DISABLED_EXTERNALLY),
})


def is_terminal(state: str) -> bool:
    """터미널 state 인지 확인 (더 이상 전이 불가능).
    Whether a state is terminal (no further transitions allowed).
    """
    return state in {LEGACY, ACTUALLY_MERGED, DISABLED_EXTERNALLY, DIRECT_MERGED}
