"""`run_blocking` — 동기 함수를 워커 스레드에서 **끝까지** 돌린다.

`run_blocking` runs a sync function in a worker thread to completion, even across cancellation.

계기 — 실제 스레드와 실제 `Task.cancel()`. 스케줄러 `stop()` 이 쓰는 바로 그 취소다.
`run_in_threadpool` 만 쓰면 이 취소는 스레드를 둔 채 곧바로 올라온다 — 그래서 대조군으로
같은 시나리오를 `run_in_threadpool` 에도 태워, 계기가 그 차이를 실제로 본다는 것을 보인다.
Instrument: real threads and a real Task.cancel() (what the scheduler's stop() does). The same
scenario is run through bare run_in_threadpool as the control that the instrument sees the gap.
"""
from __future__ import annotations

import asyncio
import threading
import time

import anyio
import pytest
from starlette.concurrency import run_in_threadpool

from src.shared.off_loop import run_blocking
from src.shared.rls_context import get_rls_user_id, reset_rls_user_id, set_rls_user_id


async def test_returns_the_result_from_a_worker_thread():
    loop_thread = threading.current_thread()
    result = await run_blocking(lambda a, *, b: (a + b, threading.current_thread()), 2, b=3)
    assert result[0] == 5
    assert result[1] is not loop_thread


async def test_propagates_the_functions_exception():
    def boom():
        raise LookupError("from the worker")

    with pytest.raises(LookupError, match="from the worker"):
        await run_blocking(boom)


async def test_the_worker_sees_the_callers_rls_user_id():
    """스레드풀이 contextvars 를 넘기지 않으면 운영 PG 의 RLS 가 deny-all 이 된다."""
    token = set_rls_user_id(4242)
    try:
        seen = await run_blocking(get_rls_user_id)
    finally:
        reset_rls_user_id(token)
    assert seen == 4242


async def _cancel_mid_thread(runner, *, cancels: int = 1) -> dict:
    """0.3 s 걸리는 스레드 작업 도중 태스크를 `cancels` 번 취소하고 시각을 적는다."""
    marks: dict = {}

    def work():
        marks["start"] = time.perf_counter()
        time.sleep(0.3)
        marks["end"] = time.perf_counter()

    async def caller():
        try:
            await runner(work)
        finally:
            marks["raised"] = time.perf_counter()

    task = asyncio.create_task(caller())
    await asyncio.sleep(0.05)
    for _ in range(cancels):
        task.cancel()
        await asyncio.sleep(0.02)
    with pytest.raises(asyncio.CancelledError):
        await task
    marks["cancelled"] = task.cancelled()
    # 대조군이 남긴 스레드가 다음 테스트로 새지 않게 끝날 때까지 기다린다.
    # Let a thread the control left running finish before the next test.
    while "end" not in marks:
        await asyncio.sleep(0.01)
    return marks


@pytest.mark.parametrize("cancels", [1, 3])
async def test_cancellation_is_raised_only_after_the_thread_finished(cancels):
    """🔴 취소는 스레드가 끝난 **뒤에** 올라온다 — 그 전에 올라오면 호출자의 finally(세션 close)가
    아직 쓰이는 세션을 다른 스레드에서 만진다. 여러 번 취소해도 같다."""
    marks = await _cancel_mid_thread(run_blocking, cancels=cancels)
    assert marks["cancelled"], "태스크가 취소로 끝나지 않았다 — 취소를 삼켰다"
    assert marks["raised"] >= marks["end"], (
        f"스레드가 끝나기 {marks['end'] - marks['raised']:.3f}s 전에 취소가 올라왔다")


async def test_anyio_scope_cancellation_waits_without_spinning_the_loop():
    """🔴 anyio 취소 범위(요청·webhook 경로)는 대기 중인 태스크를 **매 루프마다** 다시 취소한다 —
    재대기가 그 취소를 또 받으면 스레드가 끝날 때까지 루프 CPU 를 태운다(리뷰 실측: 0.5 s 남은
    스레드에 루프 CPU ≈0.45 s, 취소 7만여 회). 재대기는 막혀야 하고, 취소는 여전히 스레드 뒤에 올라온다.
    anyio cancel scopes re-cancel the waiter on every loop pass; the re-wait must be shielded so the
    loop idles while the thread finishes, and the cancellation still surfaces after the thread."""
    marks: dict = {}

    def work():
        time.sleep(0.4)
        marks["end"] = time.perf_counter()

    cpu0 = time.thread_time()
    with anyio.CancelScope() as scope:
        async def cancel_soon():
            await anyio.sleep(0.05)
            scope.cancel()

        async with anyio.create_task_group() as tg:
            tg.start_soon(cancel_soon)
            try:
                await run_blocking(work)
            finally:
                marks["raised"] = time.perf_counter()
    loop_cpu = time.thread_time() - cpu0

    assert scope.cancelled_caught, "범위가 취소를 받지 않았다 — 취소를 삼켰다"
    assert marks["raised"] >= marks["end"], "스레드가 끝나기 전에 취소가 올라왔다"
    # 스레드는 0.35 s 더 잔다 — 헛돌면 루프 CPU 가 그만큼 탄다. 막힌 재대기는 거의 0.
    # The thread sleeps ~0.35 s more; a spinning re-wait burns that on the loop thread.
    assert loop_cpu < 0.15, f"취소 뒤 재대기가 루프 CPU {loop_cpu:.3f}s 를 태웠다 — 헛돈다"


async def test_control_bare_run_in_threadpool_raises_before_the_thread_ends():
    """대조군 — `run_in_threadpool` 은 `Task.cancel()` 에 스레드를 기다리지 않는다(실측).
    이 차이가 없다면 `run_blocking` 은 필요 없다. 계기가 그 차이를 본다는 증거이기도 하다.
    Control: bare run_in_threadpool raises before the thread ends — the reason run_blocking exists."""
    marks = await _cancel_mid_thread(run_in_threadpool)
    assert marks["raised"] < marks["end"]
