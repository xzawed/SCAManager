"""Native Auto-Merge orchestration 단위 테스트 — Tier 3 PR-A.
Native Auto-Merge orchestration unit tests — Tier 3 PR-A.

테스트 대상 — `src.gate.native_automerge.enable_or_fallback`
  - enable 성공 / 폴백 / 즉시 실패 분기 (6 가지 status 경로)
  - expected_sha 전달 여부에 따른 get_pr_mergeable_state 호출 제어
  - merge_pr 폴백 결과 그대로 반환 검증
"""
import os

# 환경변수는 src 임포트 전 주입 필수
# Env vars must be injected before any src import
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")

from unittest.mock import AsyncMock, patch

import httpx

from src.gate.native_automerge import enable_or_fallback
from src.github_client.graphql import (
    ENABLE_API_ERROR,
    ENABLE_DISABLED_IN_REPO,
    ENABLE_FORCE_PUSHED,
    ENABLE_OK,
    ENABLE_PERMISSION_DENIED,
    EnableAutoMergeResult,
)

TOKEN = "ghp_testtoken"
REPO = "owner/myrepo"
PR = 17
NODE_ID = "PR_kwDO_NodeId123"
HEAD_SHA = "deadbeef1234567890"
CALLER_SHA = "caller_sha_aabbccdd"


# ── 헬퍼 ────────────────────────────────────────────────────────────────────
# ── Helpers ─────────────────────────────────────────────────────────────────


def _patch_native(
    *,
    enable_result: EnableAutoMergeResult,
    merge_result: tuple = (True, None, HEAD_SHA),
    node_id: str | None = NODE_ID,
    state_result: tuple | Exception = ("clean", HEAD_SHA),
):
    """공통 patch helper — enable, merge_pr, get_pr_node_id, get_pr_mergeable_state mock 묶음.
    Common patch helper that wires up enable, merge_pr, node_id, mergeable_state mocks.

    호출자가 with-stack 으로 사용해 각 mock 의 호출 검증 가능.
    Caller uses as a with-stack to assert call counts on each mock.
    """
    enable_mock = AsyncMock(return_value=enable_result)
    merge_mock = AsyncMock(return_value=merge_result)
    node_id_mock = AsyncMock(return_value=node_id)
    if isinstance(state_result, Exception):
        state_mock = AsyncMock(side_effect=state_result)
    else:
        state_mock = AsyncMock(return_value=state_result)

    return (
        patch("src.gate.native_automerge.enable_pull_request_auto_merge", enable_mock),
        patch("src.gate.native_automerge.merge_pr", merge_mock),
        patch("src.gate.native_automerge.get_pr_node_id", node_id_mock),
        patch("src.gate.native_automerge.get_pr_mergeable_state", state_mock),
        enable_mock, merge_mock, node_id_mock, state_mock,
    )


# ── 시나리오 1: enable 성공 ────────────────────────────────────────────────
# ── Scenario 1: enable success ─────────────────────────────────────────────


async def test_enable_success_returns_ok():
    """enable → ENABLE_OK → (True, None, head_sha) 반환, merge_pr 미호출.
    enable → ENABLE_OK → returns (True, None, head_sha); merge_pr is NOT called.
    """
    p_enable, p_merge, p_node, p_state, enable_mock, merge_mock, _, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_OK),
    )
    with p_enable, p_merge, p_node, p_state:
        ok, reason, sha = await enable_or_fallback(
            TOKEN, REPO, PR, expected_sha=CALLER_SHA,
        )

    assert ok is True
    assert reason is None
    assert sha == CALLER_SHA
    enable_mock.assert_awaited_once()
    merge_mock.assert_not_called()


# ── 시나리오 2: 폴백 가능 status — DISABLED / PERMISSION_DENIED ────────────
# ── Scenario 2: fallback-eligible status — DISABLED / PERMISSION_DENIED ────


async def test_enable_disabled_in_repo_falls_back_to_merge_pr():
    """enable → ENABLE_DISABLED_IN_REPO → merge_pr 폴백 결과 그대로 반환.
    enable → ENABLE_DISABLED_IN_REPO → falls back to merge_pr and returns its result.
    """
    fallback_result = (True, None, HEAD_SHA)
    p_enable, p_merge, p_node, p_state, enable_mock, merge_mock, _, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_DISABLED_IN_REPO, "settings off"),
        merge_result=fallback_result,
    )
    with p_enable, p_merge, p_node, p_state:
        result = await enable_or_fallback(TOKEN, REPO, PR, expected_sha=HEAD_SHA)

    assert result == fallback_result
    enable_mock.assert_awaited_once()
    merge_mock.assert_awaited_once()


async def test_enable_permission_denied_falls_back_to_merge_pr():
    """enable → ENABLE_PERMISSION_DENIED → merge_pr 폴백 (REST 권한은 있을 수 있음).
    enable → ENABLE_PERMISSION_DENIED → falls back to merge_pr (REST may still work).
    """
    fallback_result = (True, None, HEAD_SHA)
    p_enable, p_merge, p_node, p_state, _, merge_mock, _, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_PERMISSION_DENIED, "no graphql perm"),
        merge_result=fallback_result,
    )
    with p_enable, p_merge, p_node, p_state:
        result = await enable_or_fallback(TOKEN, REPO, PR, expected_sha=HEAD_SHA)

    assert result == fallback_result
    merge_mock.assert_awaited_once()


# ── 시나리오 3: 폴백 불가 — FORCE_PUSHED ────────────────────────────────────
# ── Scenario 3: no-fallback — FORCE_PUSHED ─────────────────────────────────


async def test_enable_force_pushed_returns_failure_without_fallback():
    """enable → ENABLE_FORCE_PUSHED → 즉시 (False, "force_pushed: ...", head_sha) 반환.
    enable → ENABLE_FORCE_PUSHED → immediate (False, "force_pushed: ...", head_sha).
    merge_pr 호출 안 됨 (REST 도 stale 상태로 실패할 것).
    merge_pr is NOT called (REST would also fail stale).
    """
    p_enable, p_merge, p_node, p_state, _, merge_mock, _, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_FORCE_PUSHED, "Head sha didn't match"),
    )
    with p_enable, p_merge, p_node, p_state:
        ok, reason, sha = await enable_or_fallback(
            TOKEN, REPO, PR, expected_sha=HEAD_SHA,
        )

    assert ok is False
    assert reason is not None
    assert reason.startswith("force_pushed")
    assert sha == HEAD_SHA
    merge_mock.assert_not_called()


# ── 시나리오 4: node_id 조회 실패 — 즉시 폴백 ─────────────────────────────
# ── Scenario 4: node_id lookup failure — immediate fallback ────────────────


async def test_node_id_lookup_failure_falls_back_immediately():
    """get_pr_node_id → None → enable 시도 자체 안 하고 merge_pr 호출.
    get_pr_node_id → None → skip enable entirely and call merge_pr.
    """
    fallback_result = (True, None, HEAD_SHA)
    p_enable, p_merge, p_node, p_state, enable_mock, merge_mock, node_id_mock, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_OK),  # enable 호출되면 성공이 되겠지만 호출 안 돼야 함
        merge_result=fallback_result,
        node_id=None,
    )
    with p_enable, p_merge, p_node, p_state:
        result = await enable_or_fallback(TOKEN, REPO, PR, expected_sha=HEAD_SHA)

    assert result == fallback_result
    node_id_mock.assert_awaited_once()
    enable_mock.assert_not_called()
    merge_mock.assert_awaited_once()


# ── 시나리오 5: 미분류 status — 폴백 ───────────────────────────────────────
# ── Scenario 5: unclassified status — fallback ─────────────────────────────


async def test_unclassified_status_falls_back():
    """enable → ENABLE_API_ERROR (분류 외) → merge_pr 폴백 시도.
    enable → ENABLE_API_ERROR (unclassified bucket) → falls back to merge_pr.
    """
    fallback_result = (True, None, HEAD_SHA)
    p_enable, p_merge, p_node, p_state, _, merge_mock, _, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_API_ERROR, "weird"),
        merge_result=fallback_result,
    )
    with p_enable, p_merge, p_node, p_state:
        result = await enable_or_fallback(TOKEN, REPO, PR, expected_sha=HEAD_SHA)

    assert result == fallback_result
    merge_mock.assert_awaited_once()


# ── 시나리오 6: expected_sha 처리 ──────────────────────────────────────────
# ── Scenario 6: expected_sha handling ──────────────────────────────────────


async def test_expected_sha_caller_provided_skips_get_pr_state():
    """expected_sha 가 전달되면 get_pr_mergeable_state 호출 안 됨 (중복 GET 회피).
    When expected_sha is passed, get_pr_mergeable_state is NOT called (avoid duplicate GET).
    """
    p_enable, p_merge, p_node, p_state, _, _, _, state_mock = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_OK),
    )
    with p_enable, p_merge, p_node, p_state:
        await enable_or_fallback(TOKEN, REPO, PR, expected_sha=CALLER_SHA)

    state_mock.assert_not_called()


async def test_expected_sha_none_calls_get_pr_state():
    """expected_sha=None 이면 get_pr_mergeable_state 직접 호출.
    expected_sha=None → get_pr_mergeable_state is called by the function.
    """
    p_enable, p_merge, p_node, p_state, _, _, _, state_mock = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_OK),
        state_result=("clean", HEAD_SHA),
    )
    with p_enable, p_merge, p_node, p_state:
        ok, _reason, sha = await enable_or_fallback(TOKEN, REPO, PR, expected_sha=None)

    state_mock.assert_awaited_once()
    assert ok is True
    assert sha == HEAD_SHA


async def test_get_pr_state_failure_does_not_block_enable():
    """get_pr_mergeable_state 가 httpx.HTTPError 던져도 enable 시도는 진행 (head_sha="").
    Even if get_pr_mergeable_state raises httpx.HTTPError, enable is still attempted (head_sha="").
    """
    p_enable, p_merge, p_node, p_state, enable_mock, _, _, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_OK),
        state_result=httpx.ConnectError("DNS down"),
    )
    with p_enable, p_merge, p_node, p_state:
        ok, _reason, sha = await enable_or_fallback(TOKEN, REPO, PR, expected_sha=None)

    enable_mock.assert_awaited_once()
    # head_sha 가 빈 문자열인 채로 enable 호출 → expected_head_oid 는 None 으로 전달
    # head_sha is empty → expected_head_oid is passed as None
    call_kwargs = enable_mock.await_args.kwargs
    assert call_kwargs.get("expected_head_oid") is None
    assert ok is True
    assert sha == ""


# ── 시나리오 7: 폴백 실패 reason 보존 ─────────────────────────────────────
# ── Scenario 7: fallback failure reason preserved ──────────────────────────


async def test_fallback_failure_returns_rest_reason():
    """폴백 머지 실패 시 merge_pr 의 reason 그대로 반환.
    On fallback merge failure, the merge_pr reason is returned verbatim.
    """
    rest_failure = (False, "branch_protection_blocked: required check missing", HEAD_SHA)
    p_enable, p_merge, p_node, p_state, _, _, _, _ = _patch_native(
        enable_result=EnableAutoMergeResult(ENABLE_DISABLED_IN_REPO, "off"),
        merge_result=rest_failure,
    )
    with p_enable, p_merge, p_node, p_state:
        result = await enable_or_fallback(TOKEN, REPO, PR, expected_sha=HEAD_SHA)

    assert result == rest_failure
    assert result[0] is False
    assert result[1] == "branch_protection_blocked: required check missing"
