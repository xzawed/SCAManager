"""Native Auto-Merge orchestration — Tier 3 PR-A.
Native Auto-Merge orchestration — Tier 3 PR-A.

GitHub `enablePullRequestAutoMerge` 를 우선 시도하고, 활성화 불가 / 권한 부족 /
강제 푸시 등의 상황에서는 기존 `merge_pr()` 동기 머지로 폴백한다.

Try GitHub `enablePullRequestAutoMerge` first; on conditions like
auto-merge-disabled-in-repo, permission denied, or force-push, fall back to
the existing synchronous `merge_pr()`.

설계 의도 (Tier 3 PR-A):
  - PR-A 단계는 폴백 + Issue 생성 양쪽 유지 — 기존 동작과 호환 (gentle migration)
  - PR-B 에서 1주일 검증 후 폴백 제거 + `merge_retry_service` 폐기 평가
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
from src.github_client.graphql import (
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

# 폴백을 시도해야 하는 enable 실패 status 집합
# Set of enable failure statuses where fallback to merge_pr() makes sense
# - ENABLE_DISABLED_IN_REPO: 리포 settings 에 "Allow auto-merge" 미설정 — 직접 머지 시도
# - ENABLE_PERMISSION_DENIED: GraphQL mutation 권한 없음 — REST 권한은 있을 수 있어 시도
# - ENABLE_DISABLED_IN_REPO: repo settings has "Allow auto-merge" off — try direct merge
# - ENABLE_PERMISSION_DENIED: no GraphQL permission — REST might still work
_FALLBACK_STATUSES = frozenset({ENABLE_DISABLED_IN_REPO, ENABLE_PERMISSION_DENIED})

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
    """Native auto-merge enable 시도 후 필요 시 폴백.
    Try native auto-merge enable, falling back when appropriate.

    `merge_pr()` 와 동일한 시그니처/반환 형식 — 호출자(engine.py)가 그대로 교체 가능.
    Same signature/return shape as `merge_pr()` so the caller can drop-in replace.

    Args:
        expected_sha: PR head SHA — 호출자가 이미 조회했다면 전달해 중복 GET 회피.
                      None 이면 본 함수가 직접 조회.
                      Pass to skip duplicate GET when caller already fetched it.

    Returns:
        (True, None, head_sha) — enable 성공 (GitHub 가 머지 책임 인수)
                                 또는 폴백 머지 즉시 성공
        (False, reason, head_sha) — enable 실패 + 폴백도 실패 / 폴백 미시도
        Caller should branch on ok and inspect reason for failure tag.

    참고: enable 성공 시 GitHub 가 비동기로 머지를 수행 — 실제 머지 commit 발생은
    `pull_request.closed merged=true` webhook 으로 별도 추적해야 한다 (PR-B 범위).
    Note: on enable success, GitHub will merge asynchronously; the actual merge
    commit must be tracked via the `pull_request.closed merged=true` webhook (PR-B).
    """
    # 1. PR head SHA — 호출자가 전달했으면 재사용, 아니면 조회
    # 1. PR head SHA — reuse if caller passed, otherwise fetch
    head_sha = expected_sha or ""
    if not head_sha:
        try:
            _state, head_sha = await get_pr_mergeable_state(
                github_token, repo_full_name, pr_number,
            )
        except httpx.HTTPError as exc:
            logger.warning("get_pr_mergeable_state 실패 (pr=%d): %s", pr_number, exc)

    # 2. PR node_id 조회 — GraphQL mutation 의 첫 번째 인자
    # 2. Fetch PR node_id — first argument of the GraphQL mutation
    pr_node_id = await get_pr_node_id(github_token, repo_full_name, pr_number)
    if pr_node_id is None:
        # node_id 조회 실패 — GraphQL 시도 자체 불가, 즉시 폴백
        # node_id lookup failed — can't try GraphQL, fall back immediately
        logger.warning(
            "PR node_id 조회 실패, REST merge_pr 폴백 (repo=%s, pr=%d)",
            repo_full_name, pr_number,
        )
        return await merge_pr(
            github_token, repo_full_name, pr_number,
            expected_sha=head_sha or None,
        )

    # 3. enablePullRequestAutoMerge 시도
    # 3. Try enablePullRequestAutoMerge
    result = await enable_pull_request_auto_merge(
        github_token,
        pr_node_id,
        expected_head_oid=head_sha or None,
        merge_method=merge_method,
    )

    # 4. 성공 — GitHub 가 머지 책임 인수
    # 4. Success — GitHub now owns the merge
    if result.status == ENABLE_OK:
        logger.info(
            "PR #%d native auto-merge enabled: %s (head=%s)",
            pr_number, repo_full_name, head_sha[:7] if head_sha else "?",
        )
        return (True, None, head_sha)

    # 5. 폴백 부적합 (force-push 등) — 즉시 실패 보고
    # 5. Not fallback-eligible (force-push etc.) — return failure immediately
    if result.status in _NO_FALLBACK_STATUSES:
        reason = f"{result.status}: {result.detail or ''}".rstrip(": ")
        return (False, reason, head_sha)

    # 6. 폴백 시도 — _FALLBACK_STATUSES 또는 분류 외 status 모두 폴백
    # 6. Try fallback — both _FALLBACK_STATUSES and unclassified statuses fall back
    logger.info(
        "PR #%d native enable=%s 폴백 (REST merge_pr): %s",
        pr_number, result.status, result.detail or "-",
    )
    return await merge_pr(
        github_token, repo_full_name, pr_number,
        expected_sha=head_sha or None,
    )


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
