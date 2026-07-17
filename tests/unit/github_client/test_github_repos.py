import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_list_user_repos_returns_repo_list():
    """list_user_repos는 GitHub API로 리포 목록을 반환한다."""
    from src.github_client.repos import list_user_repos

    mock_response_data = [
        {"full_name": "owner/repo-a", "private": False, "description": "Repo A"},
        {"full_name": "owner/repo-b", "private": True, "description": "Repo B"},
    ]

    mock_resp = MagicMock()
    mock_resp.json.return_value = mock_response_data
    mock_resp.raise_for_status = MagicMock()
    # pagination 루프 종료 — 미설정 시 MagicMock이 truthy라 while url: 무한 루프 → 30s 타임아웃
    # Terminate pagination loop — without this, MagicMock is truthy causing infinite while url: loop
    mock_resp.links = {}

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_resp)

        result = await list_user_repos("gho_test_token")

    assert len(result) == 2
    assert result[0]["full_name"] == "owner/repo-a"
    assert result[0]["private"] is False
    assert result[1]["full_name"] == "owner/repo-b"
    assert result[1]["private"] is True


def _repos_page(data, next_url=None):
    """list_user_repos 용 mock 응답 1페이지 — next_url 지정 시 Link 헤더 next 를 흉내낸다."""
    # Build one mocked page for list_user_repos; next_url emulates the Link header's next entry.
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    # 미설정 시 MagicMock 이 truthy → while url: 무한 루프 (기존 테스트 주석 참조)
    # Without this, MagicMock is truthy causing an infinite while url: loop.
    resp.links = {"next": {"url": next_url}} if next_url else {}
    return resp


@pytest.mark.asyncio
async def test_list_user_repos_affiliation_includes_organization_member():
    """affiliation 에 organization_member 가 포함돼야 org 저장소가 복구 경로에 노출된다.

    🔴 회귀 가드 — GitHub /user/repos 의 affiliation 은 owner/collaborator/organization_member 3값이고
    기본은 셋 전부. "owner,collaborator" 로 좁히면 팀 권한으로만 접근하는 org 리포가 목록에서
    누락 → NULL-owner org 리포의 소유권 획득이 add_repo.py:126 에서 403 으로 영구 차단된다.
    Membership assertion (not exact-string) so param order changes don't false-fail.
    """
    from src.github_client.repos import list_user_repos

    mock_resp = _repos_page([])

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_resp)

        await list_user_repos("gho_test_token")

    params = mock_client.get.call_args.kwargs["params"]
    affiliations = {v.strip() for v in params["affiliation"].split(",")}
    assert "organization_member" in affiliations, (
        f"affiliation 에 organization_member 누락 — org 저장소가 복구 경로에서 배제됨: {params['affiliation']!r}"
    )
    # 기존 2값 보존 확인 (회귀 방지 — organization_member 로 치환해버리면 안 됨)
    # Ensure the original two values survive (must be added to, not swapped for).
    assert "owner" in affiliations, f"affiliation 에서 owner 유실: {params['affiliation']!r}"
    assert "collaborator" in affiliations, f"affiliation 에서 collaborator 유실: {params['affiliation']!r}"


@pytest.mark.asyncio
async def test_list_user_repos_follows_pagination_and_drops_params_after_first_page():
    """pagination 비회귀 — Link next 를 따라 전 페이지를 수집하고 2페이지부터 params=None.

    affiliation 수정이 pagination 루프(params 재사용 금지 규약)를 깨지 않는지 봉인.
    Non-regression: the next URL already encodes the query, so params must not be re-sent.
    """
    from src.github_client.repos import list_user_repos

    page1 = _repos_page(
        [{"full_name": "org/repo-1", "private": True, "description": None}],
        next_url="https://api.github.com/user/repos?page=2",
    )
    page2 = _repos_page([{"full_name": "org/repo-2", "private": False, "description": "second"}])

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(side_effect=[page1, page2])

        result = await list_user_repos("gho_test_token")

    assert [r["full_name"] for r in result] == ["org/repo-1", "org/repo-2"]
    # description None → "" 정규화 유지
    # description None is normalized to "".
    assert result[0]["description"] == ""
    assert mock_client.get.call_count == 2
    assert mock_client.get.call_args_list[0].kwargs["params"] is not None
    assert mock_client.get.call_args_list[1].kwargs["params"] is None, (
        "2페이지 요청은 next URL 에 쿼리가 인코딩돼 있으므로 params=None 이어야 함"
    )


@pytest.mark.asyncio
async def test_create_webhook_returns_webhook_id():
    """create_webhook은 GitHub API를 호출하고 webhook_id를 반환한다."""
    from src.github_client.repos import create_webhook

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"id": 12345678}
    mock_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_resp)

        webhook_secret = "random_secret_hex"  # NOSONAR python:S6418 — test fixture, not a real secret
        result = await create_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_url="https://example.com/webhooks/github",
            secret=webhook_secret,
        )

    assert result == 12345678
    call_kwargs = mock_client.post.call_args
    posted_json = call_kwargs.kwargs["json"]
    assert posted_json["name"] == "web"
    assert posted_json["active"] is True
    assert "push" in posted_json["events"]
    assert "pull_request" in posted_json["events"]
    assert posted_json["config"]["url"] == "https://example.com/webhooks/github"
    assert posted_json["config"]["secret"] == webhook_secret


@pytest.mark.asyncio
async def test_delete_webhook_returns_true_on_204():
    """delete_webhook은 204 응답 시 True를 반환한다."""
    from src.github_client.repos import delete_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 204

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.delete = AsyncMock(return_value=mock_resp)

        result = await delete_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_id=12345678,
        )

    assert result is True


@pytest.mark.asyncio
async def test_delete_webhook_returns_false_on_error():
    """delete_webhook은 204 이외 응답 시 False를 반환한다."""
    from src.github_client.repos import delete_webhook

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.delete = AsyncMock(return_value=mock_resp)

        result = await delete_webhook(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            webhook_id=12345678,
        )

    assert result is False


# ------------------------------------------------------------------
# commit_scamanager_files 테스트
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_commit_scamanager_files_creates_new():
    # 파일이 없을 때(GET → 404) config.json과 install-hook.sh 각각 PUT 2회 호출됨
    from src.github_client.repos import commit_scamanager_files

    # GET 파일 존재 여부 조회 → 404 (파일 없음)
    # GET to check file existence → 404 (file not found).
    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 404
    mock_get_resp.json.return_value = {}

    # PUT 성공 응답
    # PUT success response.
    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 201
    mock_put_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(return_value=mock_put_resp)

        await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    # 파일 2개(config.json, install-hook.sh) 각각 PUT 호출
    assert mock_client.put.call_count == 2
    put_urls = [call.args[0] for call in mock_client.put.call_args_list]
    assert any("config.json" in url for url in put_urls)
    assert any("install-hook.sh" in url for url in put_urls)


@pytest.mark.asyncio
async def test_commit_scamanager_files_updates_existing():
    # 파일이 이미 존재할 때(GET → 200 + sha) PUT 요청에 sha가 포함됨
    # When file already exists (GET → 200 + sha), sha must be included in the PUT request.
    from src.github_client.repos import commit_scamanager_files

    existing_sha = "existingsha1234567890"

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {"sha": existing_sha}

    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 200
    mock_put_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(return_value=mock_put_resp)

        await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    # PUT 요청 body에 sha가 포함되어야 함
    assert mock_client.put.call_count == 2
    for call in mock_client.put.call_args_list:
        put_body = call.kwargs.get("json", {})
        assert put_body.get("sha") == existing_sha


@pytest.mark.asyncio
async def test_commit_scamanager_files_returns_true_on_success():
    # 모든 PUT 성공 시 True 반환
    from src.github_client.repos import commit_scamanager_files

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 404
    mock_get_resp.json.return_value = {}

    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 201
    mock_put_resp.raise_for_status = MagicMock()

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(return_value=mock_put_resp)

        result = await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    assert result is True


@pytest.mark.asyncio
async def test_commit_scamanager_files_returns_false_on_error():
    # PUT 요청 중 예외 발생(httpx.HTTPStatusError 등) 시 False 반환
    from src.github_client.repos import commit_scamanager_files

    mock_get_resp = MagicMock()
    mock_get_resp.status_code = 404
    mock_get_resp.json.return_value = {}

    with patch("src.github_client.repos.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=mock_get_resp)
        mock_client.put = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "API Error",
                request=MagicMock(),
                response=MagicMock(status_code=422),
            )
        )

        result = await commit_scamanager_files(
            token="gho_test_token",
            repo_full_name="owner/test-repo",
            server_url="https://scamanager.example.com",
            hook_token="hook-token-xyz",
        )

    assert result is False


# ------------------------------------------------------------------
# _INSTALL_HOOK_SH 회귀 테스트 — Agent SDK 요금 분리 대응 (2025-06-15)
# Regression tests for _INSTALL_HOOK_SH — Agent SDK billing split 2025-06-15
# ------------------------------------------------------------------

def test_install_hook_sh_no_claude_p():
    from src.github_client.repos import _INSTALL_HOOK_SH
    non_comment = [l for l in _INSTALL_HOOK_SH.splitlines() if not l.lstrip().startswith('#')]
    assert not any('claude -p' in l for l in non_comment)


def test_install_hook_sh_uses_anthropic_api():
    """pre-push hook 스크립트가 Anthropic API를 직접 호출해야 한다."""
    from src.github_client.repos import _INSTALL_HOOK_SH
    assert "api.anthropic.com/v1/messages" in _INSTALL_HOOK_SH, (
        "hook 스크립트에 Anthropic API 엔드포인트가 없음"
    )


def test_install_hook_sh_verify_uses_bearer_not_query_token():
    """verify 호출이 토큰을 Authorization: Bearer 헤더로 전달하고 query param 으로는 노출 안 함.
    The verify call sends the token via Authorization: Bearer header, not as a query param.

    WBS 감사 P2 — 토큰이 URL(서버/프록시 access 로그·히스토리)에 노출되던 결함 봉인.
    WBS audit P2 — seals the leak where the token appeared in the URL (server/proxy logs, history).
    """
    from src.github_client.repos import _INSTALL_HOOK_SH
    verify_lines = [l for l in _INSTALL_HOOK_SH.splitlines() if "/api/hook/verify" in l]
    assert verify_lines, "verify 호출 라인을 찾지 못함"
    verify_line = verify_lines[0]
    assert 'Authorization: Bearer ${TOKEN}' in verify_line, "verify 가 Bearer 헤더를 쓰지 않음"
    assert "token=${TOKEN}" not in verify_line, "verify URL 에 token query param 이 남아있음"


def test_install_hook_sh_reads_anthropic_api_key():
    """pre-push hook 스크립트가 ANTHROPIC_API_KEY 환경변수를 사용해야 한다."""
    from src.github_client.repos import _INSTALL_HOOK_SH
    assert "ANTHROPIC_API_KEY" in _INSTALL_HOOK_SH, (
        "hook 스크립트에 ANTHROPIC_API_KEY 참조가 없음"
    )


def test_install_hook_sh_no_claude_command_check():
    """pre-push hook 스크립트에 claude CLI 존재 여부 체크가 없어야 한다."""
    from src.github_client.repos import _INSTALL_HOOK_SH
    assert "command -v claude" not in _INSTALL_HOOK_SH, (
        "hook 스크립트에 'command -v claude' 발견 — claude CLI 불필요하므로 제거 필수"
    )
