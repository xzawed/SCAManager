"""이벤트 루프 지연 프로브 — 루프를 막는 동기 호출을 운영 로그에 남긴다.

Event-loop lag probe: a sync call that blocks the loop leaves a line in the production log.

계기 — 실제 `asyncio.sleep` 과 실제 `time.sleep`. 프로브는 짧게 자고 얼마나 늦게 깼는지 잰다.
루프 위의 `time.sleep` 은 그 늦음을 그대로 만든다(양성), 쉬는 루프는 만들지 않는다(음성).
한 창에 여러 번 막혀도 WARNING 은 한 줄이다 — 표본마다 한 줄이면 로그가 막힘만큼 불어난다.
Instrument: real asyncio.sleep and real time.sleep. A time.sleep on the loop produces the lateness
(positive), an idle loop does not (negative); several stalls in one window still log one line.
"""
from __future__ import annotations

import asyncio
import logging
import time

import pytest

from src.shared import loop_lag

_LOGGER = "src.shared.loop_lag"


def _lag_lines(caplog) -> list[logging.LogRecord]:
    """프로브가 남긴 WARNING 만 — 고정 문구 `event loop lag` 로 고른다(운영자가 grep 하는 그 문자열).
    Only the probe's WARNINGs, picked by the fixed phrase operators grep for.
    """
    return [r for r in caplog.records
            if r.name == _LOGGER and r.levelno == logging.WARNING
            and r.getMessage().startswith("event loop lag")]


async def test_blocking_call_on_the_loop_logs_one_summary_per_window(caplog):
    """🔴 루프 위 `time.sleep` 두 번 → 창이 닫힐 때 WARNING **한 줄**, 두 표본과 최대 지연을 싣는다."""
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    task = loop_lag.start_loop_lag_probe(interval=0.01, threshold=0.1, window=0.6)
    try:
        await asyncio.sleep(0.05)
        time.sleep(0.25)  # 루프를 막는다 / block the loop
        await asyncio.sleep(0.05)
        time.sleep(0.25)
        # 창이 닫히고 요약이 찍힐 때까지 루프를 돌린다 / let the window close and the summary emit
        await asyncio.sleep(0.8)
    finally:
        await loop_lag.stop_loop_lag_probe(task)

    lines = _lag_lines(caplog)
    assert len(lines) == 1, [r.getMessage() for r in lines]
    worst, over = lines[0].args[0], lines[0].args[1]
    assert worst >= 0.2, lines[0].getMessage()
    assert over == 2, lines[0].getMessage()


async def test_idle_loop_logs_nothing(caplog):
    """쉬는 루프는 창이 여러 번 닫혀도 아무것도 남기지 않는다 — 문턱 아래의 흔들림은 조용하다."""
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    task = loop_lag.start_loop_lag_probe(interval=0.01, threshold=0.25, window=0.1)
    try:
        await asyncio.sleep(0.5)
    finally:
        await loop_lag.stop_loop_lag_probe(task)

    assert not _lag_lines(caplog)
    # 양성 대조 — 프로브가 실제로 돌았다(창이 여러 번 닫혔고 표본이 있었다). 죽은 프로브의 침묵은 공허하다.
    # Positive control: windows closed with samples in them; silence from a dead probe is vacuous.
    windows = [r for r in caplog.records
               if r.name == _LOGGER and r.levelno == logging.DEBUG
               and r.getMessage().startswith("loop lag probe window")]
    assert len(windows) >= 2, [r.getMessage() for r in caplog.records]
    assert all(r.args[0] > 0 for r in windows)


async def test_stop_is_clean_and_idempotent():
    """정지는 예외를 내지 않는다 — 돌던 태스크·이미 끝난 태스크·None 모두."""
    task = loop_lag.start_loop_lag_probe()
    assert task.get_name() == loop_lag.PROBE_TASK_NAME
    await asyncio.sleep(0)
    assert not task.done()

    await loop_lag.stop_loop_lag_probe(task)
    assert task.done() and task.cancelled()
    await loop_lag.stop_loop_lag_probe(task)
    await loop_lag.stop_loop_lag_probe(None)


async def test_stop_inside_a_task_being_cancelled_returns_quietly():
    """🔴 이미 취소 중인 태스크의 정리 코드에서 불러도 예외 없이 돌아온다 — 뒤따르는 정리가 돌아야 한다.

    취소 중이라는 사실만으로 다시 던지면 `finally` 의 다음 줄이 건너뛰어진다(lifespan 이 그 자리다).
    Re-raising just because the caller is already being cancelled skips the rest of its `finally`.
    """
    probe = loop_lag.start_loop_lag_probe()
    after_stop: list[bool] = []

    async def owner():
        try:
            await asyncio.Event().wait()
        finally:
            await loop_lag.stop_loop_lag_probe(probe)
            after_stop.append(True)

    task = asyncio.create_task(owner())
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert after_stop == [True]
    assert probe.done() and probe.cancelled()


async def test_stop_itself_cancelled_from_outside_propagates():
    """정지를 기다리는 동안 바깥에서 취소되면 CancelledError 가 그대로 나간다 — 삼키면 취소가 사라진다.

    If the stopper itself is cancelled while waiting, the CancelledError must escape, not vanish.
    """
    probe = loop_lag.start_loop_lag_probe()
    stopper = asyncio.create_task(loop_lag.stop_loop_lag_probe(probe))
    await asyncio.sleep(0)  # 정지가 프로브를 취소하고 그 끝을 기다리는 자리까지 / stopper now awaits the probe
    assert not stopper.done()
    stopper.cancel()
    with pytest.raises(asyncio.CancelledError):
        await stopper

    assert stopper.cancelled()
    assert probe.done()


async def test_probe_failure_never_raises_into_the_app(caplog):
    """프로브 내부가 깨져도 앱으로 새지 않는다 — 한 번 기록하고 조용히 끝난다."""
    caplog.set_level(logging.WARNING, logger=_LOGGER)
    calls = {"n": 0}

    def broken_clock() -> float:
        calls["n"] += 1
        if calls["n"] > 3:
            raise RuntimeError("clock broke")
        return time.monotonic()

    task = loop_lag.start_loop_lag_probe(interval=0.01, threshold=0.1, window=1.0, clock=broken_clock)
    await asyncio.wait_for(asyncio.shield(task), timeout=2.0)

    assert task.done() and not task.cancelled()
    assert task.exception() is None
    assert any(r.exc_info and "loop lag probe stopped" in r.getMessage() for r in caplog.records)
    await loop_lag.stop_loop_lag_probe(task)


@pytest.mark.parametrize("kwargs", [
    {"interval": 0}, {"threshold": 0}, {"window": 0}, {"interval": -1.0},
], ids=["interval0", "threshold0", "window0", "interval-neg"])
async def test_non_positive_settings_are_refused(kwargs):
    """0 이하 간격은 바쁜 루프가 된다 — 시작 전에 거절한다."""
    with pytest.raises(ValueError):
        loop_lag.start_loop_lag_probe(**kwargs)
