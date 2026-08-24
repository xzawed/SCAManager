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


# 🔴 «머지 성공» 의 단일 정의 (2026-08-24).
#
# ## 왜 `success` 만으로는 안 되나
#
# `MergeAttempt.success` 는 「이 시도의 GitHub 호출이 성공했다」다. native auto-merge 를
# **켜기만** 한 행도 `success=True` 인데(`ENABLED_PENDING_MERGE`), 그 PR 은 영영 머지되지
# 않을 수 있다 — force-push·체크 실패·사용자 해제. 켠 뒤 꺼진 행(`DISABLED_EXTERNALLY`)도
# `success` 가 그대로 True 다(`mark_disabled_externally` 는 state 만 바꾼다).
#
# ## 왜 화이트리스트만으로도 안 되나
#
# `state IN (ACTUALLY_MERGED, DIRECT_MERGED)` 로만 세면 **운영 실적의 대부분이 사라진다**.
# 운영 primary 인 재시도 경로(`merge_retry_service`)가 오랫동안 `state` 를 넘기지 않아
# `LEGACY` 로 저장돼 왔기 때문이다 — 실측(2026-08-24): `success=True` 733행 중 **675행이
# `LEGACY`**. 그 행들이 실제로 머지됐는지는 데이터에 남은 신호로 구별할 수 없어(모든
# 성공행의 `failure_reason`·`merged_at`·`enabled_at` 이 NULL) 백필도 불가능하다.
#
# ## 그래서 하이브리드다
#
#   실제 머지 상태  ∪  «state 를 쓰지 않던 시절의 성공»
#
# 오늘의 데이터에서 옳고(733), `state` 가 모든 경로에 채워진 뒤에도 옳다(pending·disabled 제외).
#
# The single definition of "this attempt ended in a merge": `success` alone counts merges that
# were only *enabled*, and a bare whitelist drops the retry path that never set `state`.
MERGED_STATES: frozenset[str] = frozenset({ACTUALLY_MERGED, DIRECT_MERGED})


def is_merged(state: str | None, success: bool | None) -> bool:
    """이 시도가 실제 머지로 끝났는가 — KPI 의 단일 판정.

    🔴 SQL 쪽 대응물은 `merge_attempt_repo.merged_sql_predicate()` 다. 두 형태가 어긋나면
    같은 화면의 두 머지율이 갈리므로, `tests/unit/services/test_merge_kpi_definition.py`
    가 모든 (state, success) 조합에서 둘이 일치하는지 대조한다.
    """
    if state in MERGED_STATES:
        return True
    return state == LEGACY and bool(success)
