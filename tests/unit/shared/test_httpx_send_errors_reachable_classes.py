"""#1498 — `except httpx.HTTPError` → `HTTPX_SEND_ERRORS` 확대로 **새로 도달 가능해진 입력 클래스**.

🔴 verify.md §7: 게이트 분기를 완화했으면(여기서는 `except` 범위 확대) 새로 도달 가능해진
입력 클래스마다 테스트를 건다. 이 파일이 그 목록이다.

확대 전에는 `httpx.HTTPError` 하위 21종만 잡혔다. 확대 후 다음 **7종**이 새로 잡힌다:

| 클래스 | 기반 | 확대 전 | 확대 후 |
|---|---|---|---|
| `InvalidURL` | `Exception` | 빠져나감 | 잡힘 |
| `CookieConflict` | `Exception` | 빠져나감 | 잡힘 |
| `StreamError` | **`RuntimeError`** | 빠져나감 | 잡힘 |
| `StreamClosed` | `StreamError` | 빠져나감 | 잡힘 |
| `StreamConsumed` | `StreamError` | 빠져나감 | 잡힘 |
| `RequestNotRead` | `StreamError` | 빠져나감 | 잡힘 |
| `ResponseNotRead` | `StreamError` | 빠져나감 | 잡힘 |

🔴 **이 확대가 무엇을 잃는지도 함께 못박는다.** `StreamError` 계열은 `RuntimeError` 하위,
즉 「스트림 API 를 잘못 썼다」는 **프로그래밍 버그**다. 확대 전에는 ASGI 밖까지 올라가
시끄럽게 죽었고, 이제는 호출부에서 타입명만 로깅되고 삼켜진다. 그 트레이드오프를 감수한
이유는 이 리포의 호출부가 **자격증명이 담긴 URL 을 로그로 흘리지 않기 위해** 존재하기
때문이다(각 호출부 주석 참조). 대신 아래 마지막 테스트가 「`Exception` 전체를 잡지는
않는다」를 고정해, 확대가 무한정 넓어지지 않게 한다.

Widening `except httpx.HTTPError` to `HTTPX_SEND_ERRORS` makes 7 previously-escaping classes
reachable by those handlers. StreamError is a RuntimeError subclass — a programming bug that
used to crash loudly now gets swallowed; that trade is deliberate (credential-bearing URLs must
not reach uvicorn's traceback), and the last test bounds how far the widening goes.
"""
from __future__ import annotations

import httpx
import pytest

from src.shared.http_client import HTTPX_SEND_ERRORS

# 확대로 새로 도달 가능해진 7종 — verify.md §7 의 「입력 클래스」 목록.
NEWLY_REACHABLE = [
    ("InvalidURL", httpx.InvalidURL),
    ("CookieConflict", httpx.CookieConflict),
    ("StreamError", httpx.StreamError),
    ("StreamClosed", httpx.StreamClosed),
    ("StreamConsumed", httpx.StreamConsumed),
    ("RequestNotRead", httpx.RequestNotRead),
    ("ResponseNotRead", httpx.ResponseNotRead),
]


def test_the_seven_are_actually_outside_httperror():
    """계기 자기검증 — 이 7종이 정말 확대 전에는 안 잡혔는지 먼저 확인한다.

    하나라도 `HTTPError` 하위면 「새로 도달」이 아니고, 이 파일 전체가 공허해진다.
    """
    inside = [n for n, cls in NEWLY_REACHABLE if issubclass(cls, httpx.HTTPError)]
    assert not inside, f"이미 HTTPError 하위라 새로 도달한 것이 아니다: {inside}"
    assert len(NEWLY_REACHABLE) == 7, "새로 도달 가능한 클래스 수가 7이 아니다"


@pytest.mark.parametrize("name,cls", NEWLY_REACHABLE)
def test_newly_reachable_class_is_caught_after_widening(name, cls):
    """🔴 7종 각각이 확대된 핸들러에 **실제로** 잡히는지 — 클래스마다 한 건."""
    assert issubclass(cls, HTTPX_SEND_ERRORS), (
        f"{name} 이 HTTPX_SEND_ERRORS 로 안 잡힌다 — 확대가 이 클래스를 놓쳤다"
    )


@pytest.mark.parametrize("name,cls", NEWLY_REACHABLE)
def test_newly_reachable_class_would_escape_the_old_narrow_except(name, cls):
    """대조군 — 옛 좁은 절(`except httpx.HTTPError`)로는 이 7종이 **빠져나간다**.

    이것이 성립하지 않으면 이 PR 이 고치는 문제가 애초에 없었다는 뜻이다.
    """
    assert not issubclass(cls, httpx.HTTPError), (
        f"{name} 이 옛 절로도 잡혔다 — 확대의 근거가 사라진다"
    )


def test_widening_does_not_reach_bare_exception():
    """🔴 확대의 **상한** — `Exception` 전체를 잡는 데까지 가지 않는다.

    `StreamError` 가 `RuntimeError` 하위라 이 튜플은 이미 일부 `RuntimeError` 를 삼킨다.
    그 범위가 무한정 넓어지면 프로그래밍 버그가 통째로 조용해진다.
    """
    assert Exception not in HTTPX_SEND_ERRORS
    assert BaseException not in HTTPX_SEND_ERRORS
    assert RuntimeError not in HTTPX_SEND_ERRORS

    # 무관한 RuntimeError 는 여전히 통과해야 한다 — 호출부가 삼키지 않는다.
    assert not issubclass(RuntimeError, HTTPX_SEND_ERRORS)
    assert not issubclass(ValueError, HTTPX_SEND_ERRORS)
    assert not issubclass(KeyError, HTTPX_SEND_ERRORS)


def test_streamerror_family_is_the_runtimeerror_tradeoff():
    """확대가 삼키게 되는 `RuntimeError` 는 **StreamError 계열뿐**임을 못박는다."""
    swallowed = [
        cls for _, cls in NEWLY_REACHABLE
        if issubclass(cls, RuntimeError)
    ]
    assert {c.__name__ for c in swallowed} == {
        "StreamError", "StreamClosed", "StreamConsumed",
        "RequestNotRead", "ResponseNotRead",
    }, f"삼켜지는 RuntimeError 범위가 예상과 다르다: {[c.__name__ for c in swallowed]}"
