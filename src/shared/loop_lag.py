"""이벤트 루프 지연 프로브 — 루프를 막는 동기 호출을 운영 로그에 남긴다.

Event-loop lag probe: leaves a line in the production log when sync work blocks the loop.

짧게 자고(`interval`) 얼마나 늦게 깼는지 잰다. 늦음이 `threshold` 를 넘은 표본은 창(`window`)
단위로 모아 **창마다 WARNING 한 줄**만 남긴다 — 표본마다 한 줄이면 막힘이 길수록 로그가 불어난다.
운영자는 고정 문구 `event loop lag` 로 grep 한다. 루프가 막힌 동안에는 이 태스크도 깨지 못하므로,
요약은 막힘이 풀린 뒤 첫 표본에서 창이 닫힐 때 나온다.
Sleep for `interval` and measure how late the wake-up was. Samples over `threshold` are summed per
`window` into one WARNING line (operators grep `event loop lag`). A blocked loop cannot wake this
task either, so the summary appears once the stall ends and the window closes.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)

PROBE_TASK_NAME = "loop-lag-probe"
# 기본값 — 0.5 s 마다 한 번 깨므로 비용은 초당 두 번의 타이머뿐이다. 문턱은 운영 왕복(≈0.21 s)
#   한 번보다 크게 잡아 쿼리 한 개짜리 막힘은 넘긴다. 창 30 s 는 단위 테스트 기한(30 s)보다 길지 않다.
# Defaults: two timer wake-ups per second. The threshold sits above one production DB round trip
#   (~0.21 s), so a single-query stall is not reported.
LOOP_LAG_INTERVAL_SECONDS = 0.5
LOOP_LAG_THRESHOLD_SECONDS = 0.25
LOOP_LAG_WINDOW_SECONDS = 30.0


async def _probe(interval: float, threshold: float, window: float,
                 clock: Callable[[], float]) -> None:
    """프로브 본체 — 취소로만 끝난다. 내부 오류는 한 번 기록하고 조용히 끝낸다(앱으로 새지 않는다).
    Probe body; ends only by cancellation. An internal error is logged once and ends it quietly.
    """
    try:
        window_start = clock()
        samples = over = 0
        worst = 0.0
        while True:
            before = clock()
            await asyncio.sleep(interval)
            now = clock()
            lag = now - before - interval
            samples += 1
            if lag > threshold:
                over += 1
                worst = max(worst, lag)
            if now - window_start < window:
                continue
            logger.debug("loop lag probe window: samples=%d max=%.3fs", samples, worst)
            if over:
                logger.warning(
                    "event loop lag: max %.3fs, %d of %d samples over %.3fs in the last %.0fs",
                    worst, over, samples, threshold, now - window_start,
                )
            window_start, samples, over, worst = now, 0, 0, 0.0
    except asyncio.CancelledError:
        raise
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # 계측이 앱을 깨면 안 된다 — 남기고 멈춘다. 되살리면 같은 오류를 반복해 로그만 채운다.
        # Instrumentation must never break the app: log and stop rather than loop on the same error.
        logger.exception("loop lag probe stopped after an internal error")


def start_loop_lag_probe(
    *,
    interval: float = LOOP_LAG_INTERVAL_SECONDS,
    threshold: float = LOOP_LAG_THRESHOLD_SECONDS,
    window: float = LOOP_LAG_WINDOW_SECONDS,
    clock: Callable[[], float] = time.monotonic,
) -> asyncio.Task:
    """실행 중인 루프에 프로브 태스크를 띄운다 — `stop_loop_lag_probe` 로 멈춘다.
    Start the probe on the running loop; stop it with `stop_loop_lag_probe`.
    """
    if min(interval, threshold, window) <= 0:
        raise ValueError(f"loop lag probe settings must be positive: "
                         f"interval={interval} threshold={threshold} window={window}")
    return asyncio.create_task(_probe(interval, threshold, window, clock), name=PROBE_TASK_NAME)


async def stop_loop_lag_probe(task: asyncio.Task | None) -> None:
    """프로브를 취소하고 끝날 때까지 기다린다 — 이미 끝났거나 None 이어도 예외 없이 돌아간다.
    Cancel the probe and wait for it; a finished task or None returns quietly.
    """
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        # 프로브 자신의 취소만 삼킨다 — 정지를 기다리던 쪽이 취소됐으면 그대로 전파한다.
        # Swallow only the probe's own cancellation; if the caller is being cancelled, propagate.
        current = asyncio.current_task()
        if current is not None and current.cancelling():
            raise
