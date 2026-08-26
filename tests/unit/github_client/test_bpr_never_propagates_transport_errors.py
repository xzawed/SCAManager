"""호출부의 `except HTTPX_SEND_ERRORS` 가 죽어 있는 **근거**를 잡는다 (감사 C3, #1519).

`gate/engine.py::_get_ci_status_safe` 와 그 쌍둥이 `services/merge_retry_service` 는
`get_required_check_contexts` 를 `try/except HTTPX_SEND_ERRORS` 로 감싸고 있었다.
그 handler 는 **한 번도 발화할 수 없었다** — callee 가 자기 안에서 전부 삼키기 때문이다:

    except httpx.HTTPStatusError as exc:   -> contexts = _classify_bpr_http_error(...)
    except HTTPX_SEND_ERRORS as exc:       -> contexts = set()

그리고 `HTTPX_SEND_ERRORS` 는 `httpx.HTTPError` 를 포함하므로 **모든 httpx 오류의
상위 타입**이다. 요청과 응답 파싱은 통째로 그 try 안에 있다.

🔴 정확히는: **httpx 예외가** 빠져나갈 수 없다는 뜻이지 「아무 예외도 안 난다」가
아니다. try 밖의 `get_http_client()` 는 `RuntimeError` 를, f-string 안의 `repo_path()` 는
`ValueError` 를 던질 수 있고 `CancelledError` 는 `BaseException` 이다. 그러나 그것들은
**지운 handler 가 애초에 안 잡던** 타입이라 지우기 전에도 그대로 호출부 밖으로 나갔다.
이 변경은 그 축을 건드리지 않는다. (Grok 적대 검토가 이 문장의 과대주장을 짚었다.)

죽은 handler 를 남겨 두면 「여기서 네트워크 오류를 다룬다」는 거짓 인상이 남는다.
그래서 handler 를 지우고, **지워도 되는 이유**를 이 파일이 잡는다 — 누가 callee 를
전파하도록 바꾸면 여기가 먼저 red 가 되고, 실패 메시지가 호출부 두 곳을 지목한다.

대조군도 함께 둔다: `get_ci_status` 는 삼키지 **않는다**. 그래서 그쪽 handler 는
살아 있고 지우면 안 된다. 둘을 한 파일에서 재야 「일괄로 지웠다」가 아님이 보인다.

The callers dropped a handler that could never fire; this file pins the reason it could
not, and the control case where a sibling handler still must exist.
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
from src.shared.http_client import HTTPX_SEND_ERRORS  # noqa: E402

_REPO, _BRANCH, _SHA = "owner/repo", "main", "d" * 40


@pytest.fixture(autouse=True)
def _clear_cache():
    C._required_contexts_cache.clear()  # noqa: SLF001
    C._required_contexts_cooldown.clear()  # noqa: SLF001
    yield
    C._required_contexts_cache.clear()  # noqa: SLF001
    C._required_contexts_cooldown.clear()  # noqa: SLF001


def _raising_client(exc: Exception):
    client = AsyncMock()
    client.get = AsyncMock(side_effect=exc)
    return client


def _status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.github.com/x")
    return httpx.HTTPStatusError(
        str(code), request=request, response=httpx.Response(code, request=request)
    )


_TRANSPORT_ERRORS = [
    httpx.ConnectError("dns"),
    httpx.ConnectTimeout("connect"),
    httpx.ReadTimeout("read"),
    httpx.PoolTimeout("pool"),
    httpx.RemoteProtocolError("protocol"),
    httpx.InvalidURL("url"),
    httpx.StreamError("stream"),
    httpx.CookieConflict("cookie"),
]


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_every_probe_error_is_actually_in_the_caught_tuple():
    """🔴 전제 — 이 파일이 쓰는 예외가 실제로 `HTTPX_SEND_ERRORS` 다.

    아니면 「안 터졌다」가 「삼켰다」가 아니라 「애초에 대상이 아니었다」가 된다.
    """
    for exc in _TRANSPORT_ERRORS:
        assert isinstance(exc, HTTPX_SEND_ERRORS), (
            f"{type(exc).__name__} 가 HTTPX_SEND_ERRORS 밖이다 — 이 파일의 전제가 깨졌다"
        )


def test_http_status_error_is_also_a_send_error():
    """🔴 전제 — `HTTPX_SEND_ERRORS` 가 `httpx.HTTPError` 를 포함하므로 상태 오류까지 덮는다.

    이것이 「빠져나갈 httpx 예외가 없다」의 절반이다.
    """
    assert isinstance(_status_error(500), HTTPX_SEND_ERRORS)


# ─── 근거 ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("exc", _TRANSPORT_ERRORS, ids=lambda e: type(e).__name__)
@pytest.mark.asyncio
async def test_bpr_fetch_never_propagates_a_transport_error(exc):
    """통신 오류가 무엇이든 `get_required_check_contexts` 는 빈 set 을 돌려준다.

    이것이 호출부 handler 를 지우게 한 사실이다. 여기가 red 가 되면
    `gate/engine.py::_get_ci_status_safe` 와 `services/merge_retry_service` 의
    같은 함수에 `except HTTPX_SEND_ERRORS: required = None` 을 **되살려야 한다.**
    """
    with patch.object(C, "get_http_client", return_value=_raising_client(exc)):
        result = await C.get_required_check_contexts("ghp_t", _REPO, _BRANCH)
    assert result == set(), (
        f"{type(exc).__name__} 에서 빈 set 이 아니라 {result!r} 를 돌려줬다"
    )


@pytest.mark.asyncio
async def test_bpr_fetch_never_propagates_a_status_error():
    """상태 오류(500)도 전파되지 않는다 — 남는 탈출구가 없음을 닫는다."""
    with patch.object(C, "get_http_client", return_value=_raising_client(_status_error(500))):
        result = await C.get_required_check_contexts("ghp_t", _REPO, _BRANCH)
    assert result == set()


# ─── 대조군 ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ci_status_does_propagate_so_its_handler_stays_alive():
    """🔴 대조군 — `get_ci_status` 는 삼키지 않는다.

    같은 함수 안의 **두 번째** `except HTTPX_SEND_ERRORS: return "unknown"` 은
    그래서 살아 있고 지우면 안 된다. 이 대조군이 없으면 이 PR 은
    「비슷하게 생긴 handler 를 일괄로 지운 것」과 구분되지 않는다.
    """
    with patch.object(
        C, "get_http_client", return_value=_raising_client(httpx.ConnectError("net"))
    ):
        with pytest.raises(HTTPX_SEND_ERRORS):
            await C.get_ci_status("ghp_t", _REPO, _SHA)
