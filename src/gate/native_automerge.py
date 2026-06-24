"""Native Auto-Merge orchestration — Tier 3 PR-A.
Native Auto-Merge orchestration — Tier 3 PR-A.

GitHub `enablePullRequestAutoMerge` 를 우선 시도하고, 활성화 불가 / 권한 부족 /
강제 푸시 등의 상황에서는 기존 `merge_pr()` 동기 머지로 폴백한다.

Try GitHub `enablePullRequestAutoMerge` first; on conditions like
auto-merge-disabled-in-repo, permission denied, or force-push, fall back to
the existing synchronous `merge_pr()`.

운영 상태 (R13 평가 결정, 2026-06-24 — 운영 DB + GitHub API 실측):
Operational status (R13 evaluation, 2026-06-24 — verified against prod DB + GitHub API):
  - 🔴 retry 큐(merge_retry_service)가 운영 PRIMARY 머지 메커니즘 — native enable 은 매번 시도되나
    SCAManager 에선 성공 불가(전체 이력 0회). 따라서 본 native 경로는 사실상 항상 REST/retry 로 폴백.
    🔴 The retry queue is the production PRIMARY merge path — native enable is attempted every time but
    never succeeds for SCAManager (0 in all history); this native path effectively always falls back.
  - native enable 은 PR 이 required status checks 로 BLOCKED 일 때만 가능. SCAManager 는 branch protection
    부재 → PR 이 항상 UNSTABLE → enable 이 "unstable status"(UNPROCESSABLE) 로 실패. (allow_auto_merge 는
    필요조건일 뿐 충분조건 아님 — 2026-06-24 canary 로 ON 했으나 여전히 실패 확인 후 원복.)
    native enable requires the PR to be BLOCKED by required status checks; SCAManager has no branch
    protection so PRs are always UNSTABLE → enable fails with "unstable status". (allow_auto_merge is
    necessary but not sufficient — 2026-06-24 canary ON still failed, reverted.)
  - 사용자 결정(2026-06-24): native 미추구 — required checks 추가 시 수동 머지 포함 전 머지가 차단돼
    점수 기반 워크플로우와 부정합. **`merge_retry_service` 폐기 X (영구 primary)**, 938 머지 실적.
    User decision (2026-06-24): do not pursue native — adding required checks would gate all merges
    (incl. manual), mismatching the score-based model. merge_retry_service is NOT deprecated (permanent primary).
  - **MergeAttempt 로깅은 호출자(engine.py) 책임** — 본 모듈은 결과 튜플만 반환,
    `merge_pr()` 와 동일한 시그니처/의미. 호출자가 ok/reason 으로 분기 + 로깅.

Phase 3 PR-B1 추가:
  - `MergeOutcome` dataclass 신규 — path 정보 (native_enable / rest_fallback)
    호출자(engine.py) 가 state 라벨링에 활용
  - `enable_or_fallback_with_path()` 헬퍼 신규 — path 정보 포함 반환
  - 기존 `enable_or_fallback()` 시그니처는 backwards compatible 유지

Design intent (Tier 3 PR-A + PR-B1):
  - PR-A keeps both fallback and issue creation — backward-compatible (gentle migration).
  - PR-B1 adds `MergeOutcome` with `path` field so callers can distinguish
    "GitHub will merge later" (enabled_pending_merge) from "we just merged"
    (direct_merged) for accurate lifecycle state tagging.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from src.gate.github_review import (
    get_pr_mergeable_state,
    merge_pr,
)
from src.gate.merge_reasons import NETWORK_ERROR
from src.github_client.graphql import (  # noqa: F401  # pylint: disable=unused-import
    # ENABLE_DISABLED_IN_REPO + ENABLE_PERMISSION_DENIED 는 외부 (tests/unit/gate/test_native_automerge.py
    # + tests/unit/gate/test_engine_defensive_guards.py) 에서 본 모듈 경로로 import 하는 re-export 영역.
    # 메모리 `feedback-copilot-autofix-noqa-trap.md` 페어 — side-effect re-export 패턴.
    # ENABLE_DISABLED_IN_REPO + ENABLE_PERMISSION_DENIED are re-exported for external test consumers.
    ENABLE_DISABLED_IN_REPO,
    ENABLE_FORCE_PUSHED,
    ENABLE_OK,
    ENABLE_PERMISSION_DENIED,
    enable_pull_request_auto_merge,
    get_pr_node_id,
)


# Phase 3 PR-B1 — path 상수 (호출자가 lifecycle state 라벨링용)
# Phase 3 PR-B1 — path constants (callers use these to label lifecycle state)
PATH_NATIVE_ENABLE = "native_enable"
PATH_REST_FALLBACK = "rest_fallback"
PATH_NO_ATTEMPT = "no_attempt"  # 향후 확장 슬롯 (cache 사전 체크 등)


@dataclass(frozen=True)
class MergeOutcome:
    """Phase 3 PR-B1 — enable_or_fallback_with_path() 의 반환 형식.

    `merge_pr()` / 기존 `enable_or_fallback()` 의 (ok, reason, sha) 튜플에 더해
    path 필드로 GitHub 비동기 머지(enabled_pending_merge) vs 즉시 REST 머지
    (direct_merged) 를 구분한다.

    Phase 3 PR-B1 — return shape of enable_or_fallback_with_path().
    Adds a `path` field on top of the legacy (ok, reason, sha) tuple so
    callers can distinguish "GitHub will merge later" vs "we just merged".
    """

    ok: bool
    reason: str | None
    head_sha: str
    path: str  # PATH_NATIVE_ENABLE | PATH_REST_FALLBACK | PATH_NO_ATTEMPT


logger = logging.getLogger(__name__)

# 폴백 없이 즉시 실패 처리해야 하는 status
# Statuses that should be treated as immediate failure without fallback
# - ENABLE_FORCE_PUSHED: head SHA 가 이미 변경됨 — REST 머지도 stale 상태로 실패
# - ENABLE_FORCE_PUSHED: head SHA already changed — REST merge would also fail stale
_NO_FALLBACK_STATUSES = frozenset({ENABLE_FORCE_PUSHED})


async def enable_or_fallback(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    *,
    expected_sha: str | None = None,
    merge_method: str = "SQUASH",
) -> tuple[bool, str | None, str]:
    """Legacy thin wrapper around `enable_or_fallback_with_path()` — backwards compat.

    `merge_pr()` 와 동일한 (ok, reason, head_sha) 튜플 반환. 신규 코드는
    `enable_or_fallback_with_path()` 직접 사용 권장 (`MergeOutcome.path` 활용).

    Returns the legacy (ok, reason, head_sha) tuple. New callers should use
    `enable_or_fallback_with_path()` directly to access `MergeOutcome.path`.
    """
    outcome = await enable_or_fallback_with_path(
        github_token, repo_full_name, pr_number,
        expected_sha=expected_sha, merge_method=merge_method,
    )
    return (outcome.ok, outcome.reason, outcome.head_sha)


async def enable_or_fallback_with_path(
    github_token: str,
    repo_full_name: str,
    pr_number: int,
    *,
    expected_sha: str | None = None,
    merge_method: str = "SQUASH",
) -> MergeOutcome:
    """Phase 3 PR-B1: `enable_or_fallback()` 의 path-aware 버전.

    동일한 분기 로직이지만 호출자가 lifecycle state 를 라벨링할 수 있도록
    `MergeOutcome.path` 필드로 native_enable vs rest_fallback 구분.

    Phase 3 PR-B1: path-aware version of `enable_or_fallback()`.
    Same branching logic, but the caller learns whether GitHub will merge
    asynchronously (PATH_NATIVE_ENABLE) or we just merged synchronously
    (PATH_REST_FALLBACK).
    """
    # 1. PR head SHA — 호출자가 전달했으면 재사용, 아니면 조회
    head_sha = expected_sha or ""
    if not head_sha:
        try:
            _state, head_sha = await get_pr_mergeable_state(
                github_token, repo_full_name, pr_number,
            )
        except httpx.HTTPError as exc:
            logger.warning("get_pr_mergeable_state 실패 (pr=%d): %s", pr_number, exc)
        # 🔴 fail-closed (감사 보안 #2 — 2026-06-23): head_sha 미확보(전달 X + 조회 실패/빈값) 시
        # SHA 원자성 가드 없이 enable/merge_pr 을 하면 expected_head_oid=None / expected_sha=None 으로
        # 전달돼 force-push 차단 계약이 사라진다. 머지를 시도하지 않고 terminal 실패(NETWORK_ERROR)로
        # 반환한다 — engine 의 is_retriable_tag(NETWORK_ERROR)=False 라 _handle_terminal_merge_failure
        # 로 가시화(머지 안 함). 이벤트성 auto-merge 1회 드롭은 다음 webhook 이 재트리거(희소).
        # (genuine retry 미선택 사유: effective_sha="" 면 should_retry(unknown)=False + enqueue
        #  commit_sha="" 라 retriable 경로가 실제로 작동 안 함 — 사용자 결정 A=terminal.)
        # fail-closed: never enable/merge without a head-SHA guard (would lose force-push protection).
        # Return terminal NETWORK_ERROR (not retriable) → surfaced via _handle_terminal_merge_failure,
        # no merge happens. A rare double-fetch failure drops this one auto-merge; next webhook re-triggers.
        if not head_sha:
            logger.warning(
                "head_sha 미확보 — SHA 가드 없는 머지 차단 (terminal, repo=%s, pr=%d)",
                repo_full_name, pr_number,
            )
            return MergeOutcome(
                ok=False, reason=NETWORK_ERROR, head_sha="", path=PATH_NO_ATTEMPT,
            )

    # 2. PR node_id 조회
    pr_node_id = await get_pr_node_id(github_token, repo_full_name, pr_number)
    if pr_node_id is None:
        # node_id 조회 실패 — 즉시 폴백
        logger.warning(
            "PR node_id 조회 실패, REST merge_pr 폴백 (repo=%s, pr=%d)",
            repo_full_name, pr_number,
        )
        ok, reason, sha = await merge_pr(
            github_token, repo_full_name, pr_number,
            expected_sha=head_sha or None,
        )
        return MergeOutcome(ok=ok, reason=reason, head_sha=sha, path=PATH_REST_FALLBACK)

    # 3. enablePullRequestAutoMerge 시도
    result = await enable_pull_request_auto_merge(
        github_token,
        pr_node_id,
        expected_head_oid=head_sha or None,
        merge_method=merge_method,
    )

    # 4. 성공 — GitHub 가 머지 책임 인수
    if result.status == ENABLE_OK:
        logger.info(
            "PR #%d native auto-merge enabled: %s (head=%s)",
            pr_number, repo_full_name, head_sha[:7] if head_sha else "?",
        )
        return MergeOutcome(
            ok=True, reason=None, head_sha=head_sha, path=PATH_NATIVE_ENABLE,
        )

    # 5. 폴백 부적합 — 즉시 실패
    if result.status in _NO_FALLBACK_STATUSES:
        reason = f"{result.status}: {result.detail or ''}".rstrip(": ")
        return MergeOutcome(
            ok=False, reason=reason, head_sha=head_sha, path=PATH_NO_ATTEMPT,
        )

    # 6. 폴백 시도
    logger.info(
        "PR #%d native enable=%s 폴백 (REST merge_pr): %s",
        pr_number, result.status, result.detail or "-",
    )
    ok, reason, sha = await merge_pr(
        github_token, repo_full_name, pr_number,
        expected_sha=head_sha or None,
    )
    return MergeOutcome(ok=ok, reason=reason, head_sha=sha, path=PATH_REST_FALLBACK)
