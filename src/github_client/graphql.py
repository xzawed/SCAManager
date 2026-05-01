"""GitHub GraphQL API 클라이언트 — Phase Tier-3 native auto-merge 진입점.
GitHub GraphQL API client — entry point for Phase Tier-3 native auto-merge.

Tier 3 의 핵심 — `enablePullRequestAutoMerge` mutation 으로 GitHub 가
머지 대기/CI 통과 후 자동 머지 책임을 가져간다. REST `PUT /merge` 와
달리 활성화만 하고 실제 머지는 GitHub 가 비동기로 처리.

Tier 3 core — `enablePullRequestAutoMerge` mutation lets GitHub take
ownership of waiting for required checks and merging when ready,
unlike REST `PUT /merge` which is synchronous.

공개 API:
  - graphql_request(token, query, variables) — generic POST 래퍼
  - get_pr_node_id(token, repo_full_name, pr_number) — REST 로 node_id 조회
    (full GraphQL query 보다 비용 저렴)
  - enable_pull_request_auto_merge(token, pr_node_id, ...) — mutation 호출
    + 422 분류된 EnableAutoMergeResult 반환
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from src.github_client.helpers import github_api_headers
from src.shared.http_client import get_http_client

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# Phase H PR-1B-2 — 5xx 재시도 정책 (의존성 추가 없이 직접 helper)
# GitHub GraphQL 일시 5xx (502/503/504) + transient network error 재시도.
# 4xx 는 즉시 전파 (재시도 무의미). exponential backoff (1s, 2s, 4s).
# Phase H PR-1B-2 — 5xx retry policy (no external retry library):
# retry on 5xx + transient network errors; propagate 4xx immediately.
#
# **다른 채널 재사용 시 통합 힌트**:
# 본 retry 패턴은 현재 GraphQL 전용이지만 동일 정책이 다른 신뢰 API
# (Discord/Slack/n8n 은 untrusted 라 제외 — CLAUDE.md 규약 참조) 에 적용 가능.
# 신규 채널 추가 시 다음 옵션 검토:
#   1. 작은 채널 (1-2 호출) — 본 모듈 패턴 inline 복제 (의존성 0 유지)
#   2. 3+ 채널 — `src/shared/retry_helper.py` 에 `retry_on_5xx(coro_fn, *,
#      max_attempts, initial_backoff)` 추출 — 본 모듈도 wrapper 로 전환
# 통합 시점: GraphQL 외 2번째 채널 도입 시. 단일 패턴 = 한곳 사용 정책.
_GRAPHQL_MAX_ATTEMPTS = 3
_GRAPHQL_INITIAL_BACKOFF_SECONDS = 1.0

# GraphQL 응답에서 분류 가능한 결과 코드
# Result codes for classifying GraphQL responses
ENABLE_OK = "ok"
ENABLE_DISABLED_IN_REPO = "auto_merge_disabled_in_repo_settings"
ENABLE_FORCE_PUSHED = "force_pushed"
ENABLE_API_ERROR = "enable_api_error"
ENABLE_PERMISSION_DENIED = "enable_permission_denied"


@dataclass(frozen=True)
class EnableAutoMergeResult:
    """enable_pull_request_auto_merge 결과 — 분류된 status + 원문 메시지.
    Result of enable_pull_request_auto_merge — classified status + raw message.
    """

    status: str
    """ENABLE_* 상수 중 하나 — 분기 판별용 정규 태그.
    One of ENABLE_* constants — canonical tag for branching.
    """

    detail: str | None = None
    """GitHub 측 원문 메시지 (운영 디버깅용). 성공 시 None.
    Raw GitHub message for ops debugging. None on success.
    """

    @property
    def ok(self) -> bool:
        """Convenience helper — status == ENABLE_OK."""
        return self.status == ENABLE_OK


async def graphql_request(
    token: str,
    query: str,
    variables: dict | None = None,
) -> dict[str, Any]:
    """GitHub GraphQL POST — 응답 JSON 반환. 5xx/network 시 자동 재시도.
    POST a GraphQL query to GitHub. Auto-retries on 5xx and network errors.

    Phase H PR-1B-2 재시도 정책:
      - 5xx (502/503/504 등) → exponential backoff (1s, 2s) 후 재시도
      - httpx.ConnectError / TimeoutException → 동일 재시도
      - 4xx (401/403/422 등) → 즉시 전파 (재시도 무의미)
      - 최대 3회 시도 후 마지막 예외 전파 (무한 루프 차단)

    HTTPStatusError (4xx) 는 호출자에게 전파. GraphQL-level errors 는 응답
    dict 의 "errors" 키에 포함되므로 호출자가 검사해야 한다.
    """
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    client = get_http_client()  # 싱글톤 / singleton
    headers = github_api_headers(token)

    last_exc: Exception | None = None
    for attempt in range(_GRAPHQL_MAX_ATTEMPTS):
        try:
            r = await client.post(GITHUB_GRAPHQL_URL, json=payload, headers=headers)
            # 5xx 는 raise_for_status() 가 던지면 except 블록에서 재시도 판정
            # 4xx 는 즉시 전파 (인증/권한/요청 형식 오류 — 재시도 무의미)
            # 5xx raises and is retried by the except block; 4xx propagates immediately.
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            # 4xx 는 즉시 전파 — 재시도 무의미
            # 4xx propagates immediately — retry would not help
            if exc.response.status_code < 500:
                raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc

        # 마지막 시도 였으면 예외 전파, 아니면 backoff 후 재시도
        # If last attempt, propagate; otherwise back off and retry
        if attempt == _GRAPHQL_MAX_ATTEMPTS - 1:
            assert last_exc is not None
            raise last_exc
        backoff = _GRAPHQL_INITIAL_BACKOFF_SECONDS * (2 ** attempt)
        logger.warning(
            "GraphQL %s (attempt %d/%d), retrying in %.1fs",
            type(last_exc).__name__, attempt + 1, _GRAPHQL_MAX_ATTEMPTS, backoff,
        )
        await asyncio.sleep(backoff)

    # 도달 불가 — for 루프가 항상 return 또는 raise
    assert last_exc is not None  # pragma: no cover
    raise last_exc  # pragma: no cover


async def get_pr_node_id(
    token: str,
    repo_full_name: str,
    pr_number: int,
) -> str | None:
    """PR 의 GraphQL node_id 조회 — REST 경로 사용 (GraphQL 보다 저렴).
    Fetch the PR's GraphQL node_id via REST (cheaper than a GraphQL round-trip).

    실패 시 None 반환 (호출자가 분기 처리).
    Returns None on failure (caller handles fallback).
    """
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    try:
        client = get_http_client()
        r = await client.get(url, headers=github_api_headers(token))
        r.raise_for_status()
        return r.json().get("node_id")
    except httpx.HTTPError as exc:
        logger.warning(
            "get_pr_node_id 실패 (repo=%s, pr=%d): %s",
            repo_full_name, pr_number, exc,
        )
        return None


# enable_pull_request_auto_merge GraphQL mutation
# expectedHeadOid 로 force-push 보호 (REST `PUT /merge` 의 sha 파라미터와 동일 의미)
# expectedHeadOid guards against force-push (same semantics as REST `PUT /merge` sha param)
_ENABLE_AUTO_MERGE_MUTATION = """
mutation EnableAutoMerge(
  $pullRequestId: ID!,
  $mergeMethod: PullRequestMergeMethod!,
  $expectedHeadOid: GitObjectID
) {
  enablePullRequestAutoMerge(input: {
    pullRequestId: $pullRequestId,
    mergeMethod: $mergeMethod,
    expectedHeadOid: $expectedHeadOid
  }) {
    pullRequest {
      number
      autoMergeRequest {
        enabledAt
        mergeMethod
      }
    }
  }
}
"""


def _classify_graphql_errors(errors: list[dict]) -> EnableAutoMergeResult:
    """GraphQL errors 배열을 EnableAutoMergeResult 로 분류.
    Classify GraphQL errors array into an EnableAutoMergeResult.

    GitHub 의 errors[].type / message 패턴을 기반으로 ENABLE_* 태그 결정.
    Based on GitHub's errors[].type / message patterns to choose ENABLE_* tag.
    """
    # 첫 번째 에러만 검사 — GitHub 은 보통 단일 에러만 반환
    # Inspect only the first error — GitHub typically returns a single error
    err = errors[0] if errors else {}
    err_type = (err.get("type") or "").upper()
    err_msg = err.get("message") or ""
    msg_lower = err_msg.lower()

    # Phase 3 PR-B2 — 이중 enable 가드: 이미 enabled 인 PR 에 mutation 재호출 시
    # GitHub 가 "already" 류 메시지로 응답. 이 경우 ENABLE_OK 로 처리해 폴백을
    # 차단 — 폴백이 일어나면 REST PUT/merge 가 405 (Not Mergeable) 로 실패하여
    # 잘못된 advice 와 Issue 가 사용자에게 발송됨 (14-에이전트 감사 R2-C 식별).
    # Phase 3 PR-B2 — double-enable guard: when GitHub returns an "already enabled"
    # message for a PR that already has auto-merge active, classify as ENABLE_OK
    # to skip fallback. Otherwise the REST PUT/merge fallback returns 405 and we
    # surface a misleading "Auto Merge 실패" alert (audit R2-C).
    if "already" in msg_lower and (
        "auto merge" in msg_lower
        or "auto-merge" in msg_lower
        or "merge state" in msg_lower
    ):
        return EnableAutoMergeResult(
            ENABLE_OK,
            f"idempotent: already enabled — {err_msg}",
        )

    # "Auto merge is not allowed for this repository"
    if "auto merge is not allowed" in msg_lower or "auto-merge is not allowed" in msg_lower:
        return EnableAutoMergeResult(ENABLE_DISABLED_IN_REPO, err_msg)

    # "Head sha didn't match" — force-push 발생
    # "Head sha didn't match" — force-push detected
    if "head sha" in msg_lower and "match" in msg_lower:
        return EnableAutoMergeResult(ENABLE_FORCE_PUSHED, err_msg)

    # FORBIDDEN — 권한 부족
    # FORBIDDEN — insufficient permissions
    if err_type == "FORBIDDEN":
        return EnableAutoMergeResult(ENABLE_PERMISSION_DENIED, err_msg)

    # 기타 — generic enable_api_error 로 묶음
    # Other — bucket as generic enable_api_error
    return EnableAutoMergeResult(ENABLE_API_ERROR, err_msg or err_type or None)


async def enable_pull_request_auto_merge(
    token: str,
    pr_node_id: str,
    *,
    expected_head_oid: str | None = None,
    merge_method: str = "SQUASH",
) -> EnableAutoMergeResult:
    """`enablePullRequestAutoMerge` mutation 호출 + 에러 분류.
    Call `enablePullRequestAutoMerge` mutation and classify errors.

    Args:
        token: GitHub token (OAuth User Token 또는 App installation token)
        pr_node_id: PR 의 GraphQL node_id (`get_pr_node_id` 로 사전 조회)
        expected_head_oid: PR head SHA — 지정 시 force-push 방지
        merge_method: SQUASH/MERGE/REBASE — 기본 SQUASH (Tier 3 결정 #1)

    Returns:
        EnableAutoMergeResult — status 가 ENABLE_OK 이면 GitHub 가 머지 책임 인수.
        그 외 status 는 호출자가 분기 처리 (폴백 또는 Issue 생성).

        EnableAutoMergeResult — when status is ENABLE_OK, GitHub now owns the
        merge. Other statuses must be branched by the caller (fallback / issue).
    """
    variables: dict[str, Any] = {
        "pullRequestId": pr_node_id,
        "mergeMethod": merge_method,
    }
    if expected_head_oid:
        variables["expectedHeadOid"] = expected_head_oid

    try:
        response = await graphql_request(token, _ENABLE_AUTO_MERGE_MUTATION, variables)
    except httpx.HTTPStatusError as exc:
        # HTTP-level 오류 — 401/403/5xx 등
        # HTTP-level error — 401/403/5xx etc.
        if exc.response.status_code in (401, 403):
            return EnableAutoMergeResult(
                ENABLE_PERMISSION_DENIED,
                f"HTTP {exc.response.status_code}",
            )
        return EnableAutoMergeResult(
            ENABLE_API_ERROR,
            f"HTTP {exc.response.status_code}: {exc}",
        )
    except httpx.HTTPError as exc:
        return EnableAutoMergeResult(ENABLE_API_ERROR, f"network: {exc}")

    # GraphQL-level errors
    if response.get("errors"):
        return _classify_graphql_errors(response["errors"])

    # 성공 — data.enablePullRequestAutoMerge 가 존재해야 함
    # Success — data.enablePullRequestAutoMerge must exist
    data = (response.get("data") or {}).get("enablePullRequestAutoMerge")
    if data is None:
        return EnableAutoMergeResult(
            ENABLE_API_ERROR,
            "missing enablePullRequestAutoMerge in response",
        )

    return EnableAutoMergeResult(ENABLE_OK)
