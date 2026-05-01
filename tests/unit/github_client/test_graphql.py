"""GitHub GraphQL 클라이언트 단위 테스트 — Tier 3 PR-A.
GitHub GraphQL client unit tests — Tier 3 PR-A.

테스트 대상 — `src.github_client.graphql`
  - graphql_request: POST + JSON 파싱 기본 동작
  - get_pr_node_id: REST 로 node_id 조회 + 실패 처리
  - enable_pull_request_auto_merge: GraphQL 응답 분류 (성공/disabled/force-push/permission/error)
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

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.github_client.graphql import (
    ENABLE_API_ERROR,
    ENABLE_DISABLED_IN_REPO,
    ENABLE_FORCE_PUSHED,
    ENABLE_OK,
    ENABLE_PERMISSION_DENIED,
    EnableAutoMergeResult,
    enable_pull_request_auto_merge,
    get_pr_node_id,
    graphql_request,
)

TOKEN = "ghp_testtoken"
REPO = "owner/myrepo"
NODE_ID = "PR_kwDO_NodeId123"


# ── 헬퍼 ────────────────────────────────────────────────────────────────────
# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_response(json_body: dict, status_code: int = 200) -> MagicMock:
    """정상 httpx 응답 mock 생성 — raise_for_status 는 no-op.
    Build a successful httpx response mock — raise_for_status is a no-op.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock()
    return resp


def _make_http_status_error(status_code: int) -> httpx.HTTPStatusError:
    """HTTPStatusError 인스턴스 생성 헬퍼 — response.status_code 속성 포함.
    Helper to construct an HTTPStatusError with response.status_code set.
    """
    response = MagicMock()
    response.status_code = status_code
    response.text = f"HTTP {status_code}"
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=MagicMock(),
        response=response,
    )


def _make_status_response(json_body: dict, status_code: int) -> MagicMock:
    """HTTPStatusError 를 raise_for_status 시 던지는 응답 mock.
    Response mock that raises HTTPStatusError on raise_for_status.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body
    resp.raise_for_status = MagicMock(side_effect=_make_http_status_error(status_code))
    return resp


# ── enable_pull_request_auto_merge — 분류 로직 ─────────────────────────────
# ── enable_pull_request_auto_merge — classification ────────────────────────


async def test_enable_returns_ok_on_successful_response():
    """data.enablePullRequestAutoMerge 가 채워진 응답 → status == ENABLE_OK.
    A populated data.enablePullRequestAutoMerge node yields ENABLE_OK.
    """
    success_body = {
        "data": {
            "enablePullRequestAutoMerge": {
                "pullRequest": {
                    "number": 42,
                    "autoMergeRequest": {
                        "enabledAt": "2026-04-27T00:00:00Z",
                        "mergeMethod": "SQUASH",
                    },
                }
            }
        }
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(success_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert isinstance(result, EnableAutoMergeResult)
    assert result.status == ENABLE_OK
    assert result.ok is True
    assert result.detail is None


async def test_enable_classifies_already_enabled_as_ok():
    """Phase 3 PR-B2 idempotency 가드 — "already in auto merge state" → ENABLE_OK.

    GitHub 이 이미 enabled 된 PR 에 mutation 재호출 시 응답하는 메시지를
    ENABLE_OK 로 처리. 폴백 차단 (REST PUT/merge → 405 거짓 실패 회피).
    Phase 3 PR-B2 idempotency guard — when GitHub responds "already in auto
    merge state", classify as ENABLE_OK to skip fallback (avoiding the false
    405 failure that would surface a misleading alert).
    """
    test_messages = [
        "Pull request is already in auto merge state",
        "Auto-merge is already enabled for this PR",
        "auto merge already requested",
    ]
    for msg in test_messages:
        err_body = {"errors": [{"message": msg}]}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_make_response(err_body))
        with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
            result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)
        assert result.status == "ok", (
            f"메시지 {msg!r} 가 ENABLE_OK 로 분류되어야 함 — 실제 {result.status!r}"
        )
        assert "idempotent: already enabled" in (result.detail or "")


async def test_enable_classifies_disabled_in_repo():
    """리포 settings 에 auto-merge 미활성 메시지 → ENABLE_DISABLED_IN_REPO.
    Message "Auto merge is not allowed for this repository" → ENABLE_DISABLED_IN_REPO.
    """
    err_body = {
        "errors": [
            {"message": "Auto merge is not allowed for this repository"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(err_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_DISABLED_IN_REPO
    assert "Auto merge is not allowed" in (result.detail or "")


async def test_enable_classifies_force_pushed():
    """"Head sha didn't match expected" 메시지 → ENABLE_FORCE_PUSHED.
    "Head sha didn't match expected" message → ENABLE_FORCE_PUSHED.
    """
    err_body = {
        "errors": [
            {"message": "Head sha didn't match expected"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(err_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_FORCE_PUSHED


async def test_enable_classifies_permission_denied_via_type():
    """errors[].type == "FORBIDDEN" → ENABLE_PERMISSION_DENIED.
    errors[].type == "FORBIDDEN" → ENABLE_PERMISSION_DENIED.
    """
    err_body = {
        "errors": [
            {"type": "FORBIDDEN", "message": "Resource not accessible"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(err_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_PERMISSION_DENIED


async def test_enable_classifies_unknown_as_api_error():
    """알 수 없는 type/message → ENABLE_API_ERROR (generic bucket).
    Unknown type/message classified as ENABLE_API_ERROR (generic bucket).
    """
    err_body = {
        "errors": [
            {"type": "BAD_THING", "message": "weird unknown error"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(err_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_API_ERROR


async def test_enable_returns_api_error_on_missing_data():
    """errors 없고 data.enablePullRequestAutoMerge 도 None → ENABLE_API_ERROR.
    No errors and no data.enablePullRequestAutoMerge → ENABLE_API_ERROR.
    """
    body = {"data": {"enablePullRequestAutoMerge": None}}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_API_ERROR
    assert "missing" in (result.detail or "")


async def test_enable_returns_permission_denied_on_403():
    """HTTP 403 응답 → ENABLE_PERMISSION_DENIED.
    HTTP 403 response → ENABLE_PERMISSION_DENIED.
    """
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_status_response({}, 403))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_PERMISSION_DENIED
    assert "403" in (result.detail or "")


async def test_enable_returns_api_error_on_500():
    """HTTP 500 응답 → ENABLE_API_ERROR.
    HTTP 500 response → ENABLE_API_ERROR.
    """
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_status_response({}, 500))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_API_ERROR
    assert "500" in (result.detail or "")


async def test_enable_returns_api_error_on_network_failure():
    """httpx.ConnectError → ENABLE_API_ERROR (network: prefix).
    httpx.ConnectError → ENABLE_API_ERROR (network: prefix).
    """
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("DNS failure"))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    assert result.status == ENABLE_API_ERROR
    assert "network" in (result.detail or "").lower()


# ── get_pr_node_id ─────────────────────────────────────────────────────────


async def test_get_pr_node_id_returns_value_on_success():
    """REST 응답 {"node_id": "..."} → 해당 값 반환.
    REST response with "node_id" → returns that value.
    """
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=_make_response({"node_id": "PR_123"}))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await get_pr_node_id(TOKEN, REPO, 7)

    assert result == "PR_123"


async def test_get_pr_node_id_returns_none_on_http_error():
    """httpx.HTTPError 발생 시 None 반환 (warning 로그 출력).
    On httpx.HTTPError, returns None (and logs a warning).
    """
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await get_pr_node_id(TOKEN, REPO, 7)

    assert result is None


# ── variables 페이로드 검증 ────────────────────────────────────────────────
# ── variables payload verification ─────────────────────────────────────────


async def test_enable_passes_squash_as_default_merge_method():
    """기본 호출 시 GraphQL variables 에 mergeMethod: "SQUASH" 포함.
    Default call sends mergeMethod: "SQUASH" in GraphQL variables.
    """
    success_body = {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 1}}}}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(success_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        await enable_pull_request_auto_merge(TOKEN, NODE_ID)

    call_kwargs = mock_client.post.call_args.kwargs
    payload = call_kwargs["json"]
    variables = payload["variables"]
    assert variables["mergeMethod"] == "SQUASH"
    assert variables["pullRequestId"] == NODE_ID


async def test_enable_omits_expected_head_oid_when_none():
    """expected_head_oid=None (기본) → variables 에 expectedHeadOid 키 없음.
    expected_head_oid=None (default) → no expectedHeadOid key in variables.
    """
    success_body = {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 1}}}}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(success_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        await enable_pull_request_auto_merge(TOKEN, NODE_ID, expected_head_oid=None)

    payload = mock_client.post.call_args.kwargs["json"]
    variables = payload["variables"]
    assert "expectedHeadOid" not in variables


async def test_enable_includes_expected_head_oid_when_provided():
    """expected_head_oid="abc" → variables 에 그대로 포함.
    expected_head_oid="abc" → included in variables verbatim.
    """
    success_body = {"data": {"enablePullRequestAutoMerge": {"pullRequest": {"number": 1}}}}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(success_body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        await enable_pull_request_auto_merge(TOKEN, NODE_ID, expected_head_oid="abc")

    payload = mock_client.post.call_args.kwargs["json"]
    variables = payload["variables"]
    assert variables["expectedHeadOid"] == "abc"


# ── graphql_request 기본 동작 — 보너스 sanity check ────────────────────────
# ── graphql_request basic behaviour — bonus sanity check ───────────────────


async def test_graphql_request_returns_parsed_json():
    """graphql_request 가 응답 JSON 을 그대로 반환하는지 sanity check.
    Sanity check that graphql_request returns parsed JSON as-is.
    """
    body = {"data": {"viewer": {"login": "octocat"}}}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_response(body))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client):
        result = await graphql_request(TOKEN, "{ viewer { login } }", None)

    assert result == body
    # variables 미전달 시 payload 에 키 없음 / no variables key when omitted.
    payload = mock_client.post.call_args.kwargs["json"]
    assert "variables" not in payload


# ──────────────────────────────────────────────────────────────────────────
# Phase H PR-1B-2 — 5xx 자동 재시도 (exponential backoff)
# 12-에이전트 감사 High C1 — GitHub GraphQL 일시 5xx 시 단발 실패 → 호출자
# 가 ENABLE_API_ERROR 폴백 → REST 405 → 운영 알림 noise. 5xx 재시도로 80%+
# 자동 회복.
# ──────────────────────────────────────────────────────────────────────────


async def test_graphql_request_retries_on_5xx_then_succeeds():
    """첫 응답 502 → 두 번째 200 — 자동 재시도로 정상 회복."""
    success_body = {"data": {"viewer": {"login": "octocat"}}}
    mock_client = AsyncMock()
    # 첫 호출 502, 두 번째 호출 200
    mock_client.post = AsyncMock(side_effect=[
        _make_status_response({}, 502), _make_response(success_body),
    ])

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client), \
         patch("src.github_client.graphql.asyncio.sleep", new_callable=AsyncMock):
        result = await graphql_request(TOKEN, "{ viewer { login } }")

    assert result == success_body
    # 두 번 호출됨 — 재시도 동작 확인
    assert mock_client.post.call_count == 2


async def test_graphql_request_does_not_retry_on_4xx():
    """401/403/422 등 4xx 는 즉시 전파 — 재시도 무의미."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=_make_status_response({}, 403))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client), \
         patch("src.github_client.graphql.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with pytest.raises(httpx.HTTPStatusError):
            await graphql_request(TOKEN, "{ viewer { login } }")

    # 정확히 1회 시도 (재시도 X)
    assert mock_client.post.call_count == 1
    mock_sleep.assert_not_called()


async def test_graphql_request_gives_up_after_max_attempts_on_persistent_5xx():
    """모든 시도가 5xx → 무한 루프 차단, 마지막 5xx 전파."""
    mock_client = AsyncMock()
    # 항상 503
    mock_client.post = AsyncMock(return_value=_make_status_response({}, 503))

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client), \
         patch("src.github_client.graphql.asyncio.sleep", new_callable=AsyncMock):
        with pytest.raises(httpx.HTTPStatusError):
            await graphql_request(TOKEN, "{ viewer { login } }")

    # 무한 루프 방지 — 합리적 상한 (3회 이내)
    assert 1 < mock_client.post.call_count <= 5


async def test_graphql_request_retries_on_network_error():
    """ConnectError / TimeoutException 등 transient 네트워크 오류도 재시도."""
    success_body = {"data": {"viewer": {"login": "octocat"}}}
    mock_client = AsyncMock()
    # 첫 호출 ConnectError, 두 번째 200
    mock_client.post = AsyncMock(side_effect=[
        httpx.ConnectError("DNS"), _make_response(success_body),
    ])

    with patch("src.github_client.graphql.get_http_client", return_value=mock_client), \
         patch("src.github_client.graphql.asyncio.sleep", new_callable=AsyncMock):
        result = await graphql_request(TOKEN, "{ viewer { login } }")

    assert result == success_body
    assert mock_client.post.call_count == 2
