"""`Link` 헤더의 next URL 을 따라가면 **토큰이 임의 호스트로 나간다** (#1515).

GitHub 이 준 `Link: <...>; rel="next"` 의 URL 을 그대로 요청하면 그 요청에
`Authorization: Bearer <GitHub 토큰>` 이 실린다. 응답이 변조되거나 중간 프록시가 끼면
토큰이 우리가 고르지 않은 호스트로 나간다.

## 🔴 이슈 본문의 처방은 틀렸다 — 실측

#1515 본문은 「`_same_github_origin()` 은 이미 있다(`repos.py`)」고 적었지만
`src/` 전체에 **0건**이다(2026-08-27 실측). #1514 는 origin 검증을 네 번 시도했고
CodeQL 은 그 비교를 sanitizer 로 인식하지 않았다. 통한 것은 **taint 를 없애는 것**이다:

    URL 은 우리가 만들고(`base` + 정수 `page`), 서버에게서는 「더 있는가」 **신호만** 받는다.

정본은 같은 파일의 `list_webhooks` 다. 이 파일은 그 계약을 남은 두 순회에 적용한 것을
잰다 — `repos.py::list_user_repos` 와 `checks.py::get_ci_status`.

## 왜 CI 가 이쪽을 안 잡았나

CodeQL 게이트는 **신규 alert 만** 차단한다. 기존 코드의 alert 는 등록돼 있어 통과한다.
이쪽의 초록은 **검사 통과가 아니라 면제**다.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402

from src.github_client.checks import get_ci_status  # noqa: E402
from src.github_client.repos import list_user_repos  # noqa: E402

_HOSTILE = "https://api.github.com.evil.test/user/repos?page=2"


def _resp(payload, *, next_url=None):
    """GitHub 페이지 응답 더블 — `links` 와 `headers['Link']` 를 **둘 다** 채운다.

    구현이 어느 쪽을 읽든 같은 것을 보게 해야, 이 테스트가 구현 세부에 묶이지 않는다.
    """
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = payload
    if next_url:
        resp.links = {"next": {"url": next_url, "rel": "next"}}
        resp.headers = {"Link": f'<{next_url}>; rel="next"'}
    else:
        resp.links = {}
        resp.headers = {}
    return resp


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_response_double_matches_httpx_shape():
    """🔴 더블이 httpx 실물과 같은 모양인지 먼저 잰다.

    다르면 아래 단언은 **내가 만든 허구**를 검사하는 것이 된다.
    """
    import httpx  # noqa: PLC0415

    real = httpx.Response(
        200, headers={"Link": f'<{_HOSTILE}>; rel="next"'}, json=[])
    assert real.links.get("next", {}).get("url") == _HOSTILE, "httpx links 모양이 바뀌었다"
    assert real.headers.get("Link"), "httpx headers['Link'] 모양이 바뀌었다"

    double = _resp([], next_url=_HOSTILE)
    assert double.links.get("next", {}).get("url") == _HOSTILE
    assert double.headers.get("Link") == real.headers.get("Link"), "더블과 실물이 어긋난다"


# ─── list_user_repos ─────────────────────────────────────────────────────────


def _requested_urls(client) -> list[str]:
    return [str(c.args[0]) if c.args else str(c.kwargs.get("url")) for c in client.get.call_args_list]


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["evil.test", "api.github.com.evil.test", "127.0.0.1"])
async def test_list_user_repos_never_requests_a_server_supplied_url(host):
    """🔴 서버가 준 next URL 을 **요청하지 않는다** — 그 요청에 토큰이 실린다."""
    hostile = f"https://{host}/user/repos?page=2"
    client = MagicMock()
    client.get = AsyncMock(side_effect=[
        _resp([{"full_name": "o/a", "private": False, "description": ""}], next_url=hostile),
        _resp([{"full_name": "o/b", "private": True, "description": ""}]),
    ])
    with patch("src.github_client.repos.get_http_client", return_value=client):
        repos = await list_user_repos("ghp_x")

    assert [r["full_name"] for r in repos] == ["o/a", "o/b"], "페이지네이션이 깨졌다"
    assert all(host not in u for u in _requested_urls(client)), (
        f"서버가 준 호스트로 요청했다: {_requested_urls(client)}"
    )


@pytest.mark.asyncio
async def test_list_user_repos_builds_every_url_itself():
    """모든 요청이 우리 base 를 향하고, 페이지 번호는 **우리 쪽에서** 증가한다."""
    client = MagicMock()
    client.get = AsyncMock(side_effect=[
        _resp([{"full_name": "o/a", "private": False, "description": ""}], next_url=_HOSTILE),
        _resp([{"full_name": "o/b", "private": False, "description": ""}], next_url=_HOSTILE),
        _resp([{"full_name": "o/c", "private": False, "description": ""}]),
    ])
    with patch("src.github_client.repos.get_http_client", return_value=client):
        await list_user_repos("ghp_x")

    pages = []
    for call in client.get.call_args_list:
        assert str(call.args[0]).endswith("/user/repos"), f"base 가 아니다: {call.args[0]}"
        params = call.kwargs.get("params") or {}
        assert params.get("per_page") == 100, "가장 큰 페이지를 요청하지 않는다"
        assert params.get("affiliation") == "owner,collaborator,organization_member", (
            "affiliation 3값이 두 번째 페이지부터 빠지면 org 저장소가 사라진다"
        )
        pages.append(params.get("page"))
    assert pages == [1, 2, 3], f"페이지 번호가 우리 쪽에서 증가하지 않는다: {pages}"


@pytest.mark.asyncio
async def test_list_user_repos_rejects_a_non_list_payload():
    """🔴 200 인데 본문이 list 가 아니면 거부한다 — 제너레이터가 조용히 키를 순회한다."""
    client = MagicMock()
    client.get = AsyncMock(return_value=_resp({"message": "Bad credentials"}))
    with patch("src.github_client.repos.get_http_client", return_value=client):
        with pytest.raises(ValueError, match="list"):
            await list_user_repos("ghp_x")


# ─── checks.get_ci_status ────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("host", ["evil.test", "api.github.com.evil.test"])
async def test_get_ci_status_never_requests_a_server_supplied_url(host):
    """🔴 같은 결함이 `checks.py` 에도 있다 — 여기도 토큰이 실린다."""
    hostile = f"https://{host}/repos/o/r/commits/abc/check-runs?page=2"
    client = MagicMock()
    client.get = AsyncMock(side_effect=[
        _resp({"check_runs": [{"name": "a", "status": "completed", "conclusion": "success"}]},
              next_url=hostile),
        _resp({"check_runs": [{"name": "b", "status": "completed", "conclusion": "success"}]}),
    ])
    with patch("src.github_client.checks.get_http_client", return_value=client):
        status = await get_ci_status("ghp_x", "o/r", "abc")

    assert status == "passed", f"두 페이지를 다 모으지 못했다: {status}"
    assert all(host not in u for u in _requested_urls(client)), (
        f"서버가 준 호스트로 요청했다: {_requested_urls(client)}"
    )


@pytest.mark.asyncio
async def test_get_ci_status_builds_every_url_itself():
    """페이지 번호가 우리 쪽에서 증가한다."""
    client = MagicMock()
    client.get = AsyncMock(side_effect=[
        _resp({"check_runs": [{"name": "a", "status": "completed", "conclusion": "success"}]},
              next_url=_HOSTILE),
        _resp({"check_runs": [{"name": "b", "status": "completed", "conclusion": "success"}]}),
    ])
    with patch("src.github_client.checks.get_http_client", return_value=client):
        await get_ci_status("ghp_x", "o/r", "abc")

    pages = []
    for call in client.get.call_args_list:
        assert "check-runs" in str(call.args[0]), f"base 가 아니다: {call.args[0]}"
        assert "evil" not in str(call.args[0])
        pages.append((call.kwargs.get("params") or {}).get("page"))
    assert pages == [1, 2], f"페이지 번호가 우리 쪽에서 증가하지 않는다: {pages}"
