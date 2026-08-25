"""`list_webhooks` 가 **모든** 훅을 반환하지 않는다 — 조용한 위양성 (#1504 B).

🔴 docstring 은 「리포의 **모든** GitHub 웹훅 목록을 반환한다」라고 적혀 있는데
단일 요청이다. GitHub 의 기본 페이지 크기는 30이라, 훅이 30개를 넘으면 뒤쪽은
**보이지도 않는다.**

그 결과가 두 호출부에서 각각 다르게 나쁘다:

| 호출부 | 놓치면 |
|---|---|
| `settings.py` `_detect_stale_webhook` | 이 리포의 훅이 2페이지에 있으면 stale 배너가 **영영 안 뜬다** (실패 시 False 반환 = fail-safe 라 조용하다) |
| `settings.py` `reinstall_webhook` 정리 | 2페이지의 옛 훅이 **정리되지 않는데** `cleanup_ok` 는 True 로 남아 **완전 성공으로 보고**된다 |

두 번째가 특히 나쁘다 — #1504 R1 이 방금 고친 것이 바로 「부분 성공을 완전 성공으로
보고하는」 결함인데, 이 경로로 그것이 그대로 되살아난다.

🔴 **같은 파일에 이미 관용구가 있다.** `list_user_repos` 는 `resp.links["next"]` 를
따라 모든 페이지를 모은다(`repos.py`). `list_webhooks` 만 그것을 안 한다 —
누락이지 설계 결정이 아니다.

The docstring promises every webhook but a single unpaginated request is made; GitHub's
default page size is 30. The sibling `list_user_repos` in the same file already follows
Link headers, so this is an omission rather than a decision.
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

from src.github_client.repos import list_webhooks  # noqa: E402


def _page(items, *, next_url=None):
    """GitHub 페이지 응답 더블 — `resp.links` 가 실물과 같은 모양이어야 한다."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = items
    resp.links = {"next": {"url": next_url}} if next_url else {}
    return resp


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_page_double_matches_httpx_links_shape():
    """🔴 더블의 `links` 모양이 httpx 실물과 같은지 먼저 잰다.

    모양이 다르면 아래 단언이 **내가 만든 허구**를 검사하는 것이 된다.
    httpx `Response.links` 는 `{"next": {"url": ..., "rel": "next"}}` 형태다.
    """
    import httpx  # noqa: PLC0415

    real = httpx.Response(
        200,
        headers={"Link": '<https://api.github.com/x?page=2>; rel="next"'},
        json=[],
    )
    assert real.links.get("next", {}).get("url") == "https://api.github.com/x?page=2", (
        "httpx links 모양이 바뀌었다 — 더블과 실물이 어긋난다"
    )
    assert _page([], next_url="https://api.github.com/x?page=2").links == {
        "next": {"url": "https://api.github.com/x?page=2"},
    }


# ─── 결함 — 2페이지가 통째로 사라진다 ────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_hooks_from_every_page():
    """🔴 2페이지의 훅도 반환한다 — 지금은 1페이지만 보고 끝난다.

    이 훅이 안 보이면 `reinstall_webhook` 정리가 그것을 지우지 못하는데도
    `cleanup_ok` 는 True 로 남아 **완전 성공으로 보고**된다.
    """
    client = AsyncMock()
    client.get = AsyncMock(side_effect=[
        _page([{"id": 1}, {"id": 2}], next_url="https://api.github.com/x?page=2"),
        _page([{"id": 3}]),
    ])

    with patch("src.github_client.repos.get_http_client", return_value=client):
        hooks = await list_webhooks("ghp_t", "owner/repo")

    ids = [h["id"] for h in hooks]
    assert ids == [1, 2, 3], (
        f"2페이지의 훅을 놓쳤다 — 그 훅은 정리도 안 되고 사용자에게 보고도 안 된다: {ids}"
    )
    assert client.get.await_count == 2, (
        f"다음 페이지를 요청하지 않았다 (요청 {client.get.await_count}회)"
    )


@pytest.mark.asyncio
async def test_single_page_makes_exactly_one_request():
    """대조군 — 다음 페이지가 없으면 요청은 1회다 (과잉 호출 방지)."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=_page([{"id": 1}]))

    with patch("src.github_client.repos.get_http_client", return_value=client):
        hooks = await list_webhooks("ghp_t", "owner/repo")

    assert [h["id"] for h in hooks] == [1]
    assert client.get.await_count == 1, (
        f"다음 페이지가 없는데 추가 요청을 했다 ({client.get.await_count}회)"
    )


@pytest.mark.asyncio
async def test_first_request_asks_for_the_largest_page():
    """🔴 `per_page=100` 을 요청한다 — 왕복 횟수를 줄이는 쪽이 기본값(30)보다 낫다.

    형제 `list_user_repos` 도 같은 값을 쓴다. 페이지네이션이 있으므로 100 을 넘어도
    정확성은 유지되고, 이것은 **성능**축이다.
    """
    client = AsyncMock()
    client.get = AsyncMock(return_value=_page([]))

    with patch("src.github_client.repos.get_http_client", return_value=client):
        await list_webhooks("ghp_t", "owner/repo")

    _, kwargs = client.get.await_args
    params = kwargs.get("params") or {}
    assert params.get("per_page") == 100, (
        f"첫 요청이 최대 페이지 크기를 요청하지 않는다 — 왕복이 늘어난다: {params}"
    )


@pytest.mark.asyncio
async def test_pagination_stops_and_does_not_loop_forever():
    """🔴 종료 조건 — 서버가 **같은 URL** 을 next 로 계속 주면 무한 루프가 된다.

    실물 GitHub 이 그러지는 않지만, 프록시·오설정·악의적 응답에서 가능하다.
    가드가 없으면 이 함수 하나가 워커를 묶는다.
    """
    same = "https://api.github.com/repos/owner/repo/hooks?page=2"
    client = AsyncMock()
    client.get = AsyncMock(return_value=_page([{"id": 9}], next_url=same))

    with patch("src.github_client.repos.get_http_client", return_value=client):
        with pytest.raises(ValueError):
            await list_webhooks("ghp_t", "owner/repo")

    assert client.get.await_count <= 20, (
        f"페이지 순회에 상한이 없다 — 무한 루프로 워커가 묶인다 "
        f"(요청 {client.get.await_count}회)"
    )


# ─── 잘린 목록을 완전한 것처럼 반환하지 않는다 ────────────────────────────────


@pytest.mark.asyncio
async def test_hitting_the_page_cap_raises_instead_of_returning_a_truncated_list():
    """🔴 상한에 걸리면 **던진다** — 잘린 목록을 완전한 것처럼 주면 위양성 초록이다.

    `reinstall_webhook` 은 반환된 목록을 **전부**라고 믿고 정리한 뒤 `cleanup_ok=True`
    로 완전 성공을 보고한다. 잘린 목록을 주면 못 지운 훅이 있는데도 「다 정리했다」가
    된다 — #1504 R1 이 방금 고친 그 결함이다.

    던지면 그 `except` 가 받아 **부분 성공**으로 보고한다(정확한 결과).
    `_detect_stale_webhook` 쪽은 이미 조회 실패를 False 로 흡수한다(fail-safe).
    """
    same = "https://api.github.com/repos/owner/repo/hooks?page=2"
    client = AsyncMock()
    client.get = AsyncMock(return_value=_page([{"id": 9}], next_url=same))

    with patch("src.github_client.repos.get_http_client", return_value=client):
        with pytest.raises(ValueError, match="page"):
            await list_webhooks("ghp_t", "owner/repo")


@pytest.mark.asyncio
async def test_non_list_payload_is_rejected_not_silently_spread():
    """🔴 200 인데 본문이 list 가 아니면 **거부**한다 — `extend` 가 조용히 키를 넣는다.

    실측: `[].extend({"message": "Not Found"})` → `['message']`,
    `[].extend("문자열")` → `['문','자','열']`. 둘 다 예외 없이 통과한다.
    그 쓰레기가 정리 루프로 흘러가면 `hook.get(...)` 이 엉뚱하게 터지고, 원인은
    「GitHub 이 이상한 걸 줬다」인데 로그는 전혀 다른 곳을 가리킨다.
    """
    for payload in ({"message": "Not Found"}, "문자열", 42):
        client = AsyncMock()
        client.get = AsyncMock(return_value=_page(payload))

        with patch("src.github_client.repos.get_http_client", return_value=client):
            with pytest.raises((ValueError, TypeError)):
                await list_webhooks("ghp_t", "owner/repo")


@pytest.mark.asyncio
@pytest.mark.parametrize("pages", [19, 20])
async def test_exactly_at_the_cap_returns_instead_of_raising(pages):
    """🔴 경계 — 마지막 페이지에 next 가 없으면 상한과 **같아도** 정상 반환이다.

    off-by-one 실측(Grok `01a039b2`): `if not url` 이 **다음 iteration 머리**에 있어
    `range(20)` 의 20번째 순회 뒤에는 그 검사가 실행되지 않는다. 그래서 정확히
    20페이지인 리포가 **멀쩡한데도 예외**가 났다.

    내 첫 테스트는 「같은 URL 을 계속 주는」 경우만 봐서 이 경계를 못 봤다 —
    상한 테스트가 상한 **직전/직후**를 안 보면 공허하다.
    """
    responses = []
    for i in range(1, pages + 1):
        last = i == pages
        responses.append(_page(
            [{"id": i}],
            next_url=None if last else f"https://api.github.com/x?page={i + 1}",
        ))
    client = AsyncMock()
    client.get = AsyncMock(side_effect=responses)

    with patch("src.github_client.repos.get_http_client", return_value=client):
        hooks = await list_webhooks("ghp_t", "owner/repo")

    assert [h["id"] for h in hooks] == list(range(1, pages + 1)), (
        f"{pages}페이지를 다 모으지 못했다"
    )
    assert client.get.await_count == pages
