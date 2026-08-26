"""BPR 조회 **실패**가 5분 캐시에 들어간다 — 일시 장애가 머지 판정을 5분간 오염시킨다 (감사 A5, #1519).

🔴 실측. `get_required_check_contexts` 는 모든 경로에서 빈 set 을 만들고
**무조건** 캐시에 넣는다:

    except httpx.HTTPStatusError as exc:
        contexts = _classify_bpr_http_error(...)   # 404 · 401 · 403 · 429 · 5xx 전부 set()
    except HTTPX_SEND_ERRORS:
        contexts = set()                            # 네트워크 오류도 set()

    _store_required_contexts(cache_key, contexts, now)   # <- 오류도 캐시된다

`_REQUIRED_CONTEXTS_TTL = 300`(5분)이다.

호출부는 그 빈 set 을 **「필수 체크가 없다」**로 읽고 `None` 으로 바꿔 «모든 체크 고려»
로 넘어간다(`gate/engine.py`). 즉 429 한 번이면 5분 동안:

    실제 상태            : 필수 체크 `ci/required` 만 보면 되고 그것은 통과
    캐시된 오류 결과      : 「필수 체크 없음」 -> 모든 체크 고려 -> 비필수 실패도 반영

`_classify_bpr_http_error` 의 docstring 은 404 를 「가장 흔한 **정상** 경로」라고
스스로 적는다 — 정상과 오류를 이미 알면서 캐시에서는 같이 다룬다.

이 파일이 봉인하는 것:
1. **정상 404** (BPR 미설정)는 캐시된다 — 매 요청마다 GitHub 을 때리면 안 된다.
2. **오류**(401/403/429/5xx·네트워크)는 캐시되지 **않는다** — 다음 호출이 재시도한다.

A transient 429 must not be cached as "no required checks" for the full TTL.
"""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, patch  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from src.github_client import checks as C  # noqa: E402

_REPO, _BRANCH = "owner/repo", "main"


@pytest.fixture(autouse=True)
def _clear_cache():
    C._required_contexts_cache.clear()  # noqa: SLF001
    C._required_contexts_cooldown.clear()  # noqa: SLF001
    yield
    C._required_contexts_cache.clear()  # noqa: SLF001
    C._required_contexts_cooldown.clear()  # noqa: SLF001


def _resp(status: int, body: dict | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.github.com/x")
    return httpx.Response(status, json=body if body is not None else {}, request=request)


def _client(*responses):
    client = AsyncMock()
    client.get = AsyncMock(side_effect=list(responses))
    return client


async def _call():
    return await C.get_required_check_contexts("ghp_t", _REPO, _BRANCH)


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_successful_result_is_cached():
    """🔴 전제 — 성공 결과가 캐시되는가. 안 되면 이 파일이 다른 것을 재는 것이다."""
    client = _client(_resp(200, {"contexts": ["ci/required"]}))
    with patch.object(C, "get_http_client", return_value=client):
        first = await _call()
        second = await _call()
    assert first == {"ci/required"} == second
    assert client.get.await_count == 1, (
        f"성공 결과가 캐시되지 않는다 (요청 {client.get.await_count}회) — 전제가 바뀌었다"
    )


@pytest.mark.asyncio
async def test_a_404_is_the_documented_normal_path():
    """🔴 전제 — 404 는 정상(BPR 미설정)이고 캐시되어야 한다.

    이것까지 캐시를 안 하면 BPR 없는 리포가 매 요청마다 GitHub 을 때린다.
    """
    client = _client(httpx.HTTPStatusError("404", request=_resp(404).request,
                                           response=_resp(404)))
    with patch.object(C, "get_http_client", return_value=client):
        first = await _call()
        second = await _call()
    assert first == set() == second
    assert client.get.await_count == 1, (
        f"정상 404 가 캐시되지 않는다 (요청 {client.get.await_count}회) — 과잉 호출이 된다"
    )


# ─── 결함 ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503])
async def test_http_errors_are_not_stored_as_an_answer(status: int):
    """🔴 오류 결과가 **캐시에 값으로 저장되지 않는다.**

    저장되면 일시 장애 한 번이 TTL(5분)간 「필수 체크 없음」으로 굳어, 그 사이
    머지 판정이 실제와 다른 근거로 내려진다.

    쿨다운(«잠시 묻지 않는다»)과는 다른 축이다 — 쿨다운은 값을 저장하지 않는다.
    """
    err = httpx.HTTPStatusError(str(status), request=_resp(status).request,
                                response=_resp(status))
    client = _client(err)
    with patch.object(C, "get_http_client", return_value=client):
        first = await _call()

    assert first == set(), "오류 시 빈 set 반환은 유지한다(호출부 계약)"
    assert (_REPO, _BRANCH) not in C._required_contexts_cache, (  # noqa: SLF001
        f"{status} 오류가 «답» 으로 캐시됐다: {C._required_contexts_cache}"  # noqa: SLF001
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 429, 500, 502, 503])
async def test_recovery_is_immediate_once_the_cooldown_passes(status: int):
    """🔴 쿨다운이 지나면 **곧바로** 실제 값을 읽는다 — 5분을 기다리지 않는다.

    이것이 「캐시하지 않는다」의 목적이다. 캐시했다면 회복 후에도 TTL 이 끝날 때까지
    빈 set 이 나왔다.
    """
    err = httpx.HTTPStatusError(str(status), request=_resp(status).request,
                                response=_resp(status))
    client = _client(err, _resp(200, {"contexts": ["ci/required"]}))
    with patch.object(C, "get_http_client", return_value=client):
        first = await _call()
        C._required_contexts_cooldown.clear()  # noqa: SLF001  (쿨다운 경과)
        second = await _call()

    assert first == set()
    assert second == {"ci/required"}, (
        f"{status} 회복 후에도 실제 값이 안 나온다 — 오류가 어딘가에 굳었다: {second}"
    )
    assert client.get.await_count == 2


@pytest.mark.asyncio
async def test_network_errors_are_not_stored_either():
    """🔴 네트워크 오류도 «답» 으로 저장되지 않는다 — HTTP 오류와 같은 축이다."""
    client = _client(httpx.ConnectError("dns"), _resp(200, {"contexts": ["ci/required"]}))
    with patch.object(C, "get_http_client", return_value=client):
        first = await _call()
        assert (_REPO, _BRANCH) not in C._required_contexts_cache  # noqa: SLF001
        C._required_contexts_cooldown.clear()  # noqa: SLF001
        second = await _call()

    assert first == set()
    assert second == {"ci/required"}


@pytest.mark.asyncio
async def test_an_error_does_not_evict_a_good_cached_value():
    """🔴 오류가 **이미 캐시된 정상 값**을 밀어내지 않는다."""
    err = httpx.HTTPStatusError("429", request=_resp(429).request, response=_resp(429))
    client = _client(_resp(200, {"contexts": ["ci/required"]}), err)
    with patch.object(C, "get_http_client", return_value=client):
        good = await _call()
        C._required_contexts_cache[(_REPO, _BRANCH)] = (  # noqa: SLF001
            good, C.time.monotonic() - C._REQUIRED_CONTEXTS_TTL - 1)  # TTL 만료
        after_error = await _call()

    assert good == {"ci/required"}
    assert after_error == set(), "오류 시 빈 set 반환 계약은 유지"
    cached = C._required_contexts_cache.get((_REPO, _BRANCH))  # noqa: SLF001
    assert cached is None or cached[0] == {"ci/required"}, (
        f"오류가 캐시를 오염시켰다: {cached}"
    )


# ─── 쿨다운 — 이미 rate limit 인데 계속 두드리지 않는다 ────────────────────────


@pytest.mark.asyncio
async def test_a_429_stops_us_asking_again_immediately():
    """🔴 429 뒤 곧바로 다시 묻지 않는다.

    실패를 캐시하지 않기로 하면서 생긴 새 위험이다 — 이전엔 5분 캐시가 우연히
    쿨다운 노릇을 했다(Grok 지적, session 01a03ceb). 쿨다운은 **값을 저장하지 않는다**:
    캐시는 비어 있고, 그저 잠시 묻지 않을 뿐이다.
    """
    err = httpx.HTTPStatusError("429", request=_resp(429).request, response=_resp(429))
    client = _client(err)
    with patch.object(C, "get_http_client", return_value=client):
        await _call()
        second = await _call()

    assert second == set()
    assert client.get.await_count == 1, (
        f"429 직후에도 GitHub 을 다시 때렸다 (요청 {client.get.await_count}회)"
    )
    assert (_REPO, _BRANCH) not in C._required_contexts_cache, (  # noqa: SLF001
        "쿨다운이 «답» 으로 캐시됐다 — 쿨다운과 캐시는 다른 축이다"
    )


@pytest.mark.asyncio
async def test_retry_after_is_honoured_but_capped():
    """🔴 `Retry-After` 를 쓰되 상한을 건다 — 서버 값을 그대로 믿지 않는다."""
    request = httpx.Request("GET", "https://api.github.com/x")
    resp = httpx.Response(429, json={}, request=request,
                          headers={"Retry-After": "99999"})
    err = httpx.HTTPStatusError("429", request=request, response=resp)
    client = _client(err)
    with patch.object(C, "get_http_client", return_value=client):
        await _call()

    until = C._required_contexts_cooldown[(_REPO, _BRANCH)]  # noqa: SLF001
    remaining = until - C.time.monotonic()
    assert remaining <= C._COOLDOWN_MAX + 1, (
        f"Retry-After 를 상한 없이 믿는다: {remaining}s"
    )
    assert remaining > 0


@pytest.mark.asyncio
async def test_a_404_does_not_start_a_cooldown():
    """대조군 — 정상 404 는 캐시되고 쿨다운을 만들지 않는다."""
    err = httpx.HTTPStatusError("404", request=_resp(404).request, response=_resp(404))
    client = _client(err)
    with patch.object(C, "get_http_client", return_value=client):
        await _call()

    assert (_REPO, _BRANCH) in C._required_contexts_cache  # noqa: SLF001
    assert (_REPO, _BRANCH) not in C._required_contexts_cooldown, (  # noqa: SLF001
        "정상 404 가 쿨다운을 만들었다 — BPR 없는 리포가 매번 지연된다"
    )

@pytest.mark.asyncio
async def test_a_malformed_retry_after_falls_back_and_says_so(caplog):
    """🔴 읽을 수 없는 `Retry-After` 는 기본 쿨다운으로 떨어지고 **로그를 남긴다**.

    조용히 넘기면(빈 `except`) 벤더가 헤더 형식을 바꿔도 아무도 모른다 —
    관측면이 여기 하나뿐이다. CodeQL `py/empty-except`(alert #601)가 이 자리를 짚었다.
    """
    request = httpx.Request("GET", "https://api.github.com/x")
    resp = httpx.Response(429, json={}, request=request,
                          headers={"Retry-After": "not-a-number"})
    err = httpx.HTTPStatusError("429", request=request, response=resp)
    client = _client(err)
    with caplog.at_level("WARNING"), patch.object(C, "get_http_client", return_value=client):
        await _call()

    until = C._required_contexts_cooldown[(_REPO, _BRANCH)]  # noqa: SLF001
    remaining = until - C.time.monotonic()
    assert 0 < remaining <= C._COOLDOWN_RATE_LIMIT + 1, (
        f"기본 쿨다운으로 떨어지지 않았다: {remaining}s"
    )
    assert any("Retry-After" in r.message or "Retry-After" in r.getMessage()
               for r in caplog.records), (
        "비정형 Retry-After 를 조용히 넘겼다 — 형식 변경을 관측할 방법이 없다"
    )
