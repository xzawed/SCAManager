"""Phase 4 PR-T4 — Tier 3 PR-A 시나리오 단위 테스트 (이중 enable + force-push + 분류 엣지).

기존 test_graphql.py / test_native_automerge.py 가 happy path 와 주요 분기를
다루지만, 14-에이전트 감사 R1-B 가 지적한 다음 영역의 엣지 케이스 갭이
남았다.

검증 대상:
  - _classify_graphql_errors: 빈 errors / 빈 메시지 / case-insensitive / 단어 분리 /
    "already" 단독은 OK 가 아님 / "already + auto merge" 결합 필요
  - enable_pull_request_auto_merge: REBASE/MERGE merge_method / 401 → PERMISSION /
    422 → API_ERROR / errors+data 동시 → errors 우선
  - graphql_request: variables 없을 때 payload 에 키 누락
  - enable_or_fallback (native_automerge): already-enabled 시 merge_pr 미호출 /
    빈 expected_sha → get_pr_mergeable_state 호출 / FORCE_PUSHED detail 없을 때
    rstrip 적용
  - enable_or_fallback_with_path: already-enabled → PATH_NATIVE_ENABLE 유지 /
    FORCE_PUSHED 시 PATH_NO_ATTEMPT + head_sha 보존
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# pylint: disable=wrong-import-position
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.gate.native_automerge import (
    PATH_NATIVE_ENABLE,
    PATH_NO_ATTEMPT,
    enable_or_fallback,
    enable_or_fallback_with_path,
)
from src.github_client.graphql import (
    ENABLE_API_ERROR,
    ENABLE_DISABLED_IN_REPO,
    ENABLE_FORCE_PUSHED,
    ENABLE_OK,
    ENABLE_PERMISSION_DENIED,
    EnableAutoMergeResult,
    _classify_graphql_errors,
    enable_pull_request_auto_merge,
    graphql_request,
)


TOKEN = "ghp_x"
REPO = "owner/repo"
NODE_ID = "PR_kwDO_test"


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _make_response(json_body: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    return resp


def _make_status_response(status_code: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.text = f"HTTP {status_code}"
    err = httpx.HTTPStatusError(
        f"HTTP {status_code}", request=MagicMock(), response=response,
    )
    resp = MagicMock()
    resp.json.return_value = {}
    resp.raise_for_status = MagicMock(side_effect=err)
    return resp


# ──────────────────────────────────────────────────────────────────────────
# _classify_graphql_errors — 엣지 케이스
# ──────────────────────────────────────────────────────────────────────────


def test_classify_empty_errors_returns_api_error():
    """errors=[] (방어적) → ENABLE_API_ERROR with detail=None."""
    result = _classify_graphql_errors([])
    assert result.status == ENABLE_API_ERROR
    assert result.detail is None


def test_classify_empty_message_uses_type_for_detail():
    """type 만 있고 message 없을 때 detail 에 type 사용."""
    result = _classify_graphql_errors([{"type": "INTERNAL", "message": ""}])
    assert result.status == ENABLE_API_ERROR
    assert result.detail == "INTERNAL"


def test_classify_no_type_no_message_returns_api_error_none_detail():
    """type 도 message 도 없으면 detail=None."""
    result = _classify_graphql_errors([{}])
    assert result.status == ENABLE_API_ERROR
    assert result.detail is None


def test_classify_uppercase_disabled_message():
    """case-insensitive — 대문자 메시지도 동일 분류."""
    result = _classify_graphql_errors(
        [{"message": "AUTO MERGE IS NOT ALLOWED FOR THIS REPOSITORY"}]
    )
    assert result.status == ENABLE_DISABLED_IN_REPO


def test_classify_uppercase_force_pushed():
    """case-insensitive — 대문자 'HEAD SHA' 도 force-push 인식."""
    result = _classify_graphql_errors(
        [{"message": "HEAD SHA didn't match expected"}]
    )
    assert result.status == ENABLE_FORCE_PUSHED


def test_classify_already_alone_is_not_idempotent_ok():
    """'already' 단독 (auto merge / merge state 미포함) → ENABLE_API_ERROR.

    PR-B2 가드는 "already" + ("auto merge" | "auto-merge" | "merge state")
    조합일 때만 OK — 단어 단독으로는 false-positive 방지.
    """
    result = _classify_graphql_errors([{"message": "Resource already exists"}])
    assert result.status == ENABLE_API_ERROR


def test_classify_already_with_merge_state_is_ok():
    """'already' + 'merge state' → ENABLE_OK (idempotent 가드)."""
    result = _classify_graphql_errors(
        [{"message": "PR already in approved merge state — skip"}]
    )
    assert result.status == ENABLE_OK
    assert "idempotent: already enabled" in (result.detail or "")


def test_classify_only_inspects_first_error():
    """errors 가 여러 개 있어도 첫 번째만 분류 기준."""
    result = _classify_graphql_errors([
        {"message": "Auto merge is not allowed for this repository"},
        {"type": "FORBIDDEN", "message": "Different second error"},
    ])
    # 첫 번째 메시지가 disabled → DISABLED_IN_REPO (FORBIDDEN 무시)
    assert result.status == ENABLE_DISABLED_IN_REPO


# ──────────────────────────────────────────────────────────────────────────
# enable_pull_request_auto_merge — merge method + HTTP status edges
# ──────────────────────────────────────────────────────────────────────────


async def test_enable_passes_rebase_merge_method():
    """merge_method='REBASE' 가 GraphQL variables 에 그대로 전달."""
    success_body = {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 1}}}}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(success_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        await enable_pull_request_auto_merge(TOKEN, NODE_ID, merge_method="REBASE")

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["variables"]["mergeMethod"] == "REBASE"


async def test_enable_passes_merge_merge_method():
    """merge_method='MERGE' 가 GraphQL variables 에 전달."""
    success_body = {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 1}}}}
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(success_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        await enable_pull_request_auto_merge(TOKEN, NODE_ID, merge_method="MERGE")

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["variables"]["mergeMethod"] == "MERGE"


async def test_enable_returns_permission_denied_on_401():
    """HTTP 401 응답 → ENABLE_PERMISSION_DENIED (403 과 동일 분류)."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_status_response(401))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)
    assert result.status == ENABLE_PERMISSION_DENIED
    assert "401" in (result.detail or "")


async def test_enable_returns_api_error_on_422():
    """HTTP 422 응답 (401/403 외) → ENABLE_API_ERROR."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_status_response(422))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)
    assert result.status == ENABLE_API_ERROR
    assert "422" in (result.detail or "")


async def test_enable_errors_take_priority_over_data():
    """response 에 errors 와 data 모두 있으면 errors 분류 우선."""
    body = {
        "errors": [{"message": "Head sha didn't match expected"}],
        "data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 1}}},
    }
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)
    # errors 분류가 우선 (data 무시)
    assert result.status == ENABLE_FORCE_PUSHED


# ──────────────────────────────────────────────────────────────────────────
# graphql_request — variables 처리
# ──────────────────────────────────────────────────────────────────────────


async def test_graphql_request_omits_variables_when_none():
    """variables=None 호출 시 payload 에 'variables' 키 부재."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response({"data": {}}))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        await graphql_request(TOKEN, "{ viewer { login } }", variables=None)

    payload = mock_client.post.call_args.kwargs["json"]
    assert "variables" not in payload
    assert payload["query"] == "{ viewer { login } }"


async def test_graphql_request_includes_variables_when_provided():
    """variables 제공 시 payload 에 그대로 포함."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response({"data": {}}))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        await graphql_request(TOKEN, "query Q($n: Int!) { node(id: $n) { id } }", variables={"n": 42})

    payload = mock_client.post.call_args.kwargs["json"]
    assert payload["variables"] == {"n": 42}


# ──────────────────────────────────────────────────────────────────────────
# enable_or_fallback — already-enabled (Phase 3 PR-B2)
# ──────────────────────────────────────────────────────────────────────────


async def test_already_enabled_does_not_call_merge_pr():
    """이미 enabled 인 PR 에 mutation 재호출 → ENABLE_OK 가드 → merge_pr 미호출.

    PR #115 (Phase 3 PR-B2) 의 핵심 시나리오 — 폴백 차단으로 405 false failure 방지.
    """
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_OK, "idempotent: already enabled — already in auto merge state"),
    ), patch("src.gate.native_automerge.merge_pr", new_callable=AsyncMock) as mock_merge_pr:
        ok, reason, sha = await enable_or_fallback(
            TOKEN, REPO, 42, expected_sha="abc",
        )

    assert ok is True
    assert reason is None
    assert sha == "abc"
    # 핵심 — REST 폴백 미호출 (PR-B2 가드 핵심)
    mock_merge_pr.assert_not_called()


async def test_already_enabled_with_path_returns_native_enable_path():
    """with_path 버전: already-enabled 시 PATH_NATIVE_ENABLE 유지 (PATH_REST_FALLBACK 아님)."""
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_OK, "idempotent"),
    ), patch("src.gate.native_automerge.merge_pr", new_callable=AsyncMock) as mock_merge_pr:
        outcome = await enable_or_fallback_with_path(
            TOKEN, REPO, 42, expected_sha="abc",
        )

    assert outcome.ok is True
    assert outcome.path == PATH_NATIVE_ENABLE
    assert outcome.head_sha == "abc"
    mock_merge_pr.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────
# enable_or_fallback — expected_sha 빈 문자열 처리
# ──────────────────────────────────────────────────────────────────────────


async def test_empty_string_expected_sha_triggers_get_state_lookup():
    """expected_sha='' 도 None 처럼 처리 → get_pr_mergeable_state 호출."""
    with patch(
        "src.gate.native_automerge.get_pr_mergeable_state",
        new_callable=AsyncMock,
        return_value=("clean", "real_sha"),
    ) as mock_state, patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_OK),
    ):
        ok, _reason, sha = await enable_or_fallback(
            TOKEN, REPO, 42, expected_sha="",
        )

    mock_state.assert_called_once()
    assert ok is True
    assert sha == "real_sha"  # get_pr_mergeable_state 결과 사용


# ──────────────────────────────────────────────────────────────────────────
# Force-push: detail 없을 때 reason rstrip
# ──────────────────────────────────────────────────────────────────────────


async def test_force_pushed_with_no_detail_strips_trailing_colon():
    """FORCE_PUSHED detail=None 일 때 reason 이 깔끔한 'force_pushed' (콜론 없음)."""
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_FORCE_PUSHED, None),
    ):
        ok, reason, _ = await enable_or_fallback(
            TOKEN, REPO, 42, expected_sha="abc",
        )

    assert ok is False
    # rstrip(": ") 적용 — "force_pushed" 끝에 콜론 없음
    assert reason == ENABLE_FORCE_PUSHED
    assert not reason.endswith(":")
    assert not reason.endswith(": ")


async def test_force_pushed_with_path_returns_no_attempt_path():
    """with_path 버전: FORCE_PUSHED 는 PATH_NO_ATTEMPT (REST 폴백 안 시도)."""
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_FORCE_PUSHED, "Head sha mismatch"),
    ), patch("src.gate.native_automerge.merge_pr", new_callable=AsyncMock) as mock_merge_pr:
        outcome = await enable_or_fallback_with_path(
            TOKEN, REPO, 42, expected_sha="caller_sha",
        )

    assert outcome.ok is False
    assert outcome.path == PATH_NO_ATTEMPT
    assert outcome.head_sha == "caller_sha"  # 보존 (force-push 라도 caller SHA 유지)
    # FORCE_PUSHED 는 폴백 안 함 (REST PUT/merge 도 stale 로 실패할 것)
    mock_merge_pr.assert_not_called()


async def test_force_pushed_reason_includes_detail_when_present():
    """FORCE_PUSHED detail 이 있을 때 'force_pushed: <detail>' 형태."""
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(
            ENABLE_FORCE_PUSHED, "Head sha didn't match expected",
        ),
    ):
        _ok, reason, _ = await enable_or_fallback(
            TOKEN, REPO, 42, expected_sha="abc",
        )

    assert reason.startswith(ENABLE_FORCE_PUSHED)
    assert "Head sha didn't match" in reason


# ──────────────────────────────────────────────────────────────────────────
# enable_or_fallback merge_method 전파
# ──────────────────────────────────────────────────────────────────────────


async def test_enable_or_fallback_passes_rebase_merge_method():
    """merge_method='REBASE' 가 enable_pull_request_auto_merge 까지 전달."""
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_OK),
    ) as mock_enable:
        await enable_or_fallback(
            TOKEN, REPO, 42, expected_sha="abc", merge_method="REBASE",
        )

    call_kwargs = mock_enable.call_args.kwargs
    assert call_kwargs["merge_method"] == "REBASE"


async def test_enable_or_fallback_with_path_passes_merge_merge_method():
    """with_path 변종도 merge_method 전파 — 'MERGE' 검증."""
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_OK),
    ) as mock_enable:
        await enable_or_fallback_with_path(
            TOKEN, REPO, 42, expected_sha="abc", merge_method="MERGE",
        )

    call_kwargs = mock_enable.call_args.kwargs
    assert call_kwargs["merge_method"] == "MERGE"


# ──────────────────────────────────────────────────────────────────────────
# expected_head_oid 전달 일관성
# ──────────────────────────────────────────────────────────────────────────


async def test_enable_or_fallback_passes_expected_head_oid():
    """caller 가 expected_sha 전달 시 enable_pull_request_auto_merge 의 expected_head_oid 로 전달."""
    with patch(
        "src.gate.native_automerge.get_pr_node_id",
        new_callable=AsyncMock,
        return_value="node",
    ), patch(
        "src.gate.native_automerge.enable_pull_request_auto_merge",
        new_callable=AsyncMock,
        return_value=EnableAutoMergeResult(ENABLE_OK),
    ) as mock_enable:
        await enable_or_fallback(TOKEN, REPO, 42, expected_sha="forced_sha")

    call_kwargs = mock_enable.call_args.kwargs
    assert call_kwargs["expected_head_oid"] == "forced_sha"
