"""동기(블로킹) 작업을 워커 스레드에서 끝까지 돌린다 — 취소가 와도 스레드가 끝난 뒤에 올린다.

Run blocking work in a worker thread to completion; a cancellation is re-raised only after the
thread has finished.

동기 DB 문장을 이벤트 루프에서 돌리면 왕복마다 프로세스의 모든 요청이 선다(운영 왕복 ≈ 0.2 s).
`starlette.concurrency.run_in_threadpool` 이 그 일을 하지만, 요청 밖(스케줄러)에서는 하나가 모자라다:
anyio 취소 범위(요청 처리)는 스레드를 기다리지만 `Task.cancel()`(스케줄러 `stop()`)은 **스레드를
둔 채 곧바로 올라온다**(실측 — `tests/unit/shared/test_off_loop.py` 대조군). 그러면 호출자의
`finally` 가 닫는 세션을 스레드가 아직 쓰고 있다 — 한 세션을 두 스레드가 동시에 만진다.
Sync DB on the loop stalls every request per round trip. run_in_threadpool waits for its thread
under anyio cancellation, but a plain Task.cancel() returns at once, so a caller's finally could
close a session the thread is still using.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

import anyio
from starlette.concurrency import run_in_threadpool

T = TypeVar("T")


async def run_blocking(fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
    """`fn(*args, **kwargs)` 를 워커 스레드에서 돌려 결과를 돌려준다(contextvars 전달 — RLS 사용자 id 포함).

    Run `fn` in a worker thread and return its result; contextvars (the RLS user id) are carried.

    취소가 오면 스레드가 끝날 때까지 기다린 뒤 그 취소를 그대로 올린다. 스레드의 결과·예외는
    버린다 — 호출자는 이미 취소됐다. 스레드는 멈출 수 없으므로 기다리는 것 말고는 방법이 없다.
    On cancellation, wait for the thread, then re-raise the cancellation (the thread's own result or
    exception is dropped — the caller is already cancelled).
    """
    work = asyncio.ensure_future(run_in_threadpool(fn, *args, **kwargs))
    interrupted: asyncio.CancelledError | None = None
    while not work.done():
        try:
            # `asyncio.wait` 는 취소돼도 기다리던 퓨처를 취소하지 않는다(`wait_for`·`gather` 와 다르다).
            # asyncio.wait never cancels the awaited future when the waiter is cancelled.
            if interrupted is None:
                await asyncio.wait((work,))
            else:
                # 🔴 anyio 취소 범위는 대기자를 루프마다 다시 취소한다 — 막지 않으면 스레드가 끝날
                # 때까지 루프가 헛돈다(리뷰 실측 ≈0.45 s CPU/0.5 s). 취소는 이미 받아 뒀다.
                # anyio scopes re-cancel the waiter every loop pass; shield the re-wait so it idles.
                with anyio.CancelScope(shield=True):
                    await asyncio.wait((work,))
        except asyncio.CancelledError as exc:
            interrupted = exc
    if interrupted is not None:
        if not work.cancelled():
            work.exception()  # 스레드의 예외를 «회수됨» 으로 — 경고 소음 차단 / mark it retrieved
        raise interrupted
    return work.result()
