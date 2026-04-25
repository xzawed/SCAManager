"""Tests for src/github_client/repos.py — commit_scamanager_files()."""
import base64
import json
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import AsyncMock, MagicMock, call, patch

import httpx
import pytest

from src.github_client.repos import commit_scamanager_files

TOKEN = "ghp_testtoken"
REPO = "owner/myrepo"
SERVER = "https://example.com"
HOOK_TOKEN = "hook_secret_abc"


def _mock_response(status_code: int, sha: str | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"sha": sha} if sha else {}
    resp.raise_for_status = MagicMock()
    return resp


def _make_client(get_responses: list, put_responses: list) -> AsyncMock:
    """GET과 PUT 각각 순서대로 응답을 반환하는 AsyncMock 클라이언트."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=get_responses)
    mock_client.put = AsyncMock(side_effect=put_responses)
    return mock_client


def _patch_client(mock_client):
    patcher = patch("src.github_client.repos.get_http_client", return_value=mock_client)
    patcher.start()
    return patcher


# ---------------------------------------------------------------------------
# 시나리오 1: 신규 파일 (GET 404) → PUT에 sha 없이 커밋
# Scenario 1: new file (GET 404) → commit via PUT without sha.
# ---------------------------------------------------------------------------

async def test_new_files_put_without_sha():
    """파일이 없을 때(GET 404) PUT body에 sha를 포함하지 않아야 한다."""
    get_404 = _mock_response(404)
    put_201 = _mock_response(201)
    client = _make_client(
        get_responses=[get_404, get_404],
        put_responses=[put_201, put_201],
    )
    patcher = _patch_client(client)
    try:
        result = await commit_scamanager_files(TOKEN, REPO, SERVER, HOOK_TOKEN)
    finally:
        patcher.stop()

    assert result is True
    # 두 PUT 호출 모두 sha 없이 전송
    # Both PUT calls must be sent without a sha.
    for put_call in client.put.call_args_list:
        body = put_call.kwargs.get("json") or put_call.args[1]
        assert "sha" not in body, "신규 파일 PUT에는 sha가 없어야 한다"


# ---------------------------------------------------------------------------
# 시나리오 2: 기존 파일 (GET 200 + sha) → PUT에 sha 포함
# Scenario 2: existing file (GET 200 + sha) → PUT request must include sha.
# ---------------------------------------------------------------------------

async def test_existing_files_put_with_sha():
    """파일이 이미 존재할 때(GET 200) PUT body에 sha를 포함해야 한다."""
    sha_config = "sha_config_abc"
    sha_hook = "sha_hook_xyz"
    client = _make_client(
        get_responses=[
            _mock_response(200, sha=sha_config),
            _mock_response(200, sha=sha_hook),
        ],
        put_responses=[_mock_response(200), _mock_response(200)],
    )
    patcher = _patch_client(client)
    try:
        result = await commit_scamanager_files(TOKEN, REPO, SERVER, HOOK_TOKEN)
    finally:
        patcher.stop()

    assert result is True
    put_calls = client.put.call_args_list
    body_0 = put_calls[0].kwargs.get("json") or put_calls[0].args[1]
    body_1 = put_calls[1].kwargs.get("json") or put_calls[1].args[1]
    assert body_0.get("sha") == sha_config
    assert body_1.get("sha") == sha_hook


# ---------------------------------------------------------------------------
# 시나리오 3: PUT 실패 → False 반환, 예외 미전파
# ---------------------------------------------------------------------------

async def test_put_http_error_returns_false():
    """PUT 호출이 HTTPError를 발생시키면 False를 반환하고 예외를 전파하지 않는다."""
    get_404 = _mock_response(404)
    bad_put = MagicMock()
    bad_put.raise_for_status.side_effect = httpx.HTTPStatusError(
        "422 Unprocessable", request=MagicMock(), response=MagicMock()
    )
    client = _make_client(
        get_responses=[get_404, get_404],
        put_responses=[bad_put, bad_put],
    )
    patcher = _patch_client(client)
    try:
        result = await commit_scamanager_files(TOKEN, REPO, SERVER, HOOK_TOKEN)
    finally:
        patcher.stop()

    assert result is False


# ---------------------------------------------------------------------------
# 시나리오 4: config.json 내용 검증
# ---------------------------------------------------------------------------

async def test_config_json_content_is_correct():
    """config.json PUT body의 content(base64)가 올바른 JSON을 담아야 한다."""
    get_404 = _mock_response(404)
    put_201 = _mock_response(201)
    client = _make_client(
        get_responses=[get_404, get_404],
        put_responses=[put_201, put_201],
    )
    patcher = _patch_client(client)
    try:
        await commit_scamanager_files(TOKEN, REPO, SERVER, HOOK_TOKEN)
    finally:
        patcher.stop()

    # 첫 번째 PUT이 config.json (files dict 순서 기준)
    config_put = client.put.call_args_list[0]
    body = config_put.kwargs.get("json") or config_put.args[1]
    decoded = json.loads(base64.b64decode(body["content"]).decode())
    assert decoded["server"] == SERVER
    assert decoded["repo"] == REPO
    assert decoded["token"] == HOOK_TOKEN


# ---------------------------------------------------------------------------
# 시나리오 5: server_url trailing slash 제거
# ---------------------------------------------------------------------------

async def test_server_url_trailing_slash_stripped():
    """server_url에 trailing slash가 있어도 config에는 제거되어 저장된다."""
    get_404 = _mock_response(404)
    put_201 = _mock_response(201)
    client = _make_client(
        get_responses=[get_404, get_404],
        put_responses=[put_201, put_201],
    )
    patcher = _patch_client(client)
    try:
        await commit_scamanager_files(TOKEN, REPO, "https://example.com/", HOOK_TOKEN)
    finally:
        patcher.stop()

    config_put = client.put.call_args_list[0]
    body = config_put.kwargs.get("json") or config_put.args[1]
    decoded = json.loads(base64.b64decode(body["content"]).decode())
    assert not decoded["server"].endswith("/"), "server URL 끝에 슬래시가 없어야 한다"
    assert decoded["server"] == "https://example.com"


# ---------------------------------------------------------------------------
# 시나리오 6: Authorization 헤더 포함 확인
# ---------------------------------------------------------------------------

async def test_auth_header_included_in_requests():
    """모든 GET/PUT 요청에 Bearer 토큰이 포함된 Authorization 헤더가 전송되어야 한다."""
    get_404 = _mock_response(404)
    put_201 = _mock_response(201)
    client = _make_client(
        get_responses=[get_404, get_404],
        put_responses=[put_201, put_201],
    )
    patcher = _patch_client(client)
    try:
        await commit_scamanager_files(TOKEN, REPO, SERVER, HOOK_TOKEN)
    finally:
        patcher.stop()

    for get_call in client.get.call_args_list:
        headers = get_call.kwargs.get("headers") or {}
        assert headers.get("Authorization") == f"Bearer {TOKEN}"

    for put_call in client.put.call_args_list:
        headers = put_call.kwargs.get("headers") or {}
        assert headers.get("Authorization") == f"Bearer {TOKEN}"
