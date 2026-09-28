"""run_analysis_pipeline 동시 실행 상한 — 새 웹훅의 202 가 N 개 넘는 파이프라인 뒤에 줄 서지 않게.

Concurrency cap for run_analysis_pipeline — a new webhook's 202 never waits behind more than
N pipelines' synchronous DB blocks on the event loop.

계약 / Contract
---------------
- 본문(첫 DB 블록 `_ensure_repo` ~ 마지막 단계 `_send_notifications`) 안에 동시에 있는 파이프라인은
  `PIPELINE_MAX_CONCURRENCY` 개를 넘지 않는다. 나머지는 버려지지 않고 도착 순서대로 기다린다.
- 상한은 `src/constants.py` 의 그 상수다 — 1 로 바꾸면 직렬로 돈다.
- 본문이 예외로 끝나도 슬롯은 반환된다. 본문은 자기가 쥔 슬롯을 다시 기다리지 않는다.
- 기다려야 하는 파이프라인만 INFO 로 대기 수를 남긴다.
At most N pipelines are inside the body at once; the rest wait FIFO and all complete. N is the
named constant. A raising body frees its slot; the body never re-acquires its own slot. Only
pipelines that have to wait log at INFO.
"""
# pylint: disable=redefined-outer-name
import asyncio
import logging
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import src.constants as constants
import src.worker.pipeline as pipeline
from src.github_client.diff import ChangedFile

_LIMIT = "src.worker.pipeline.PIPELINE_MAX_CONCURRENCY"


def _sha(i: int) -> str:
    # 0 번도 all-zeros(브랜치 삭제 SHA)가 되지 않게 +1 — 그러면 본문이 시작도 안 하고 끝난다.
    # +1 so index 0 is not the all-zeros branch-delete SHA, which returns before the body starts.
    return f"{i + 1:040x}"


def _push(i: int) -> dict:
    return {
        "repository": {"full_name": "owner/repo"},
        "after": _sha(i),
        "head_commit": {"id": _sha(i), "message": f"p{i}"},
    }


class _Probe:
    """본문 안에 있는 파이프라인 수를 센다 — 들어감 = `_ensure_repo`, 나감 = `_send_notifications`.

    Counts pipelines inside the body — enter = `_ensure_repo`, leave = `_send_notifications`.
    AI 리뷰 단계에서 테스트가 풀어 줄 때까지 멈춰 선다(`release`). 저장·알림도 루프에 양보해,
    슬롯이 꼬리(저장·알림) 전에 풀리면 기다리던 것이 그 사이 들어와 수가 넘친다.
    Each pipeline parks in the AI-review stage until released. Save and notify also yield, so a
    slot freed before the tail would let a waiter in meanwhile and overflow the count.
    """

    def __init__(self) -> None:
        self.inside = 0
        self.max_inside = 0
        self.started: list[str] = []
        self.finished: list[str] = []
        self.parked: set[str] = set()
        self.fail_after_release: set[str] = set()
        self._gates: dict[str, asyncio.Event] = {}

    def _gate(self, key: str) -> asyncio.Event:
        return self._gates.setdefault(key, asyncio.Event())

    def release(self, i: int) -> None:
        self._gate(f"p{i}").set()

    def release_all(self) -> None:
        for i in range(64):
            self.release(i)

    # --- 파이프라인 본문에 끼우는 가짜들 / fakes wired into the pipeline body ---------------

    def ensure_repo(self, _db, _repo_name, commit_sha):
        self.inside += 1
        self.max_inside = max(self.max_inside, self.inside)
        self.started.append(commit_sha)
        return MagicMock(id=1), "tok"

    async def review_code(self, _api_key, commit_message, _patches, **_kw):
        self.parked.add(commit_message)
        await self._gate(commit_message).wait()
        self.parked.discard(commit_message)
        if commit_message in self.fail_after_release:
            self.inside -= 1
            raise RuntimeError("simulated review failure")
        return MagicMock()

    @staticmethod
    def build_notification_tasks(**kw):
        return [], [kw["commit_sha"]]

    @staticmethod
    async def save_and_gate(_db, _params):
        await asyncio.sleep(0.01)
        return MagicMock(), 1, {"score": 80}

    async def send_notifications(self, _tasks, names):
        await asyncio.sleep(0)
        self.inside -= 1
        self.finished.append(names[0])


async def _until(cond, timeout: float = 3.0) -> None:
    """조건이 설 때까지 루프를 돌린다 — `_collect_files` 가 실제 스레드(to_thread)라 sleep(0) 로는 부족.

    Spin the loop until cond() holds — `_collect_files` runs in a real thread (to_thread).
    """
    deadline = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached before timeout")
        await asyncio.sleep(0.005)


@pytest.fixture
def probe():
    p = _Probe()
    with (
        patch("src.worker.pipeline.SessionLocal") as session_cls,
        patch("src.worker.pipeline._ensure_repo", side_effect=p.ensure_repo),
        patch("src.worker.pipeline._begin_attempt"),
        patch("src.worker.pipeline._finish_attempt"),
        patch("src.worker.pipeline._collect_files",
              return_value=[ChangedFile("app.py", "x = 1\n", "@@ +1 @@")]),
        patch("src.worker.pipeline._resolve_review_language", return_value="en"),
        patch("src.worker.pipeline.get_repo_config",
              return_value=MagicMock(review_model=None, ai_review_enabled=True)),
        patch("src.worker.pipeline._run_static_with_timeout",
              new_callable=AsyncMock, return_value=([], False)),
        patch("src.worker.pipeline.review_code", side_effect=p.review_code),
        patch("src.worker.pipeline.calculate_score", return_value=MagicMock(total=80)),
        patch("src.worker.pipeline._save_and_gate", side_effect=p.save_and_gate),
        patch("src.worker.pipeline.build_notification_tasks",
              side_effect=p.build_notification_tasks),
        patch("src.worker.pipeline._send_notifications", side_effect=p.send_notifications),
    ):
        db = MagicMock()
        db.__enter__ = MagicMock(return_value=db)
        db.__exit__ = MagicMock(return_value=False)
        session_cls.return_value = db
        yield p


def _launch(n: int) -> list[asyncio.Task]:
    return [asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(i))) for i in range(n)]


async def test_at_most_limit_pipelines_are_inside_the_body(probe):
    """상한 2 에서 6 개를 한꺼번에 띄우면 본문 안은 늘 2 개 이하, 슬롯이 빌 때마다 다음 차례가 들어온다.

    With a limit of 2 and 6 launched at once, at most 2 are ever inside; each freed slot admits
    the next arrival, and all 6 complete.
    """
    with patch(_LIMIT, 2, create=True):
        tasks = _launch(6)
        await _until(lambda: len(probe.parked) >= 2)
        await asyncio.sleep(0.05)  # 상한이 없다면 나머지 4 개가 이 사이에 들어온다 / uncapped ones would enter here
        assert probe.inside == 2
        assert probe.started == [_sha(0), _sha(1)]

        for i in range(6):
            probe.release(i)
            await _until(lambda i=i: _sha(i) in probe.finished)
            if i + 2 < 6:
                # 빈 슬롯은 기다리던 것 중 **먼저 온 것** 이 받는다 / the freed slot goes to the oldest waiter
                await _until(lambda i=i: f"p{i + 2}" in probe.parked)
                assert probe.started[-1] == _sha(i + 2)
            assert probe.inside <= 2

        await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)

    assert probe.max_inside == 2
    assert probe.started == [_sha(i) for i in range(6)]
    assert sorted(probe.finished) == sorted(_sha(i) for i in range(6))


async def test_patching_the_constant_to_one_serialises(probe):
    """상한은 그 상수다 — 1 로 바꾸면 한 번에 하나씩, 도착 순서대로 돈다.

    The limit is the named constant — patched to 1 the pipelines run one at a time in order.
    """
    with patch(_LIMIT, 1, create=True):
        tasks = _launch(4)
        await _until(lambda: len(probe.parked) >= 1)
        await asyncio.sleep(0.05)
        assert probe.started == [_sha(0)]
        probe.release_all()
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)

    assert probe.max_inside == 1
    assert probe.started == probe.finished == [_sha(i) for i in range(4)]


async def test_default_limit_comes_from_src_constants(probe):
    """패치하지 않으면 상한 = `src.constants.PIPELINE_MAX_CONCURRENCY` — 그보다 많이 띄워 확인한다.

    Unpatched, the cap equals src.constants.PIPELINE_MAX_CONCURRENCY (launch more than that).
    """
    limit = constants.PIPELINE_MAX_CONCURRENCY
    assert limit >= 1
    tasks = _launch(limit + 2)
    await _until(lambda: len(probe.parked) >= limit)
    await asyncio.sleep(0.05)
    assert probe.inside == limit
    probe.release_all()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)
    assert probe.max_inside == limit
    assert len(probe.finished) == limit + 2


async def test_slot_is_returned_when_the_body_raises(probe):
    """본문이 예외로 끝나도(터미널 except 가 삼킨다) 슬롯이 반환돼 다음 파이프라인이 돈다.

    A body that raises (swallowed by the terminal except) still frees its slot.
    """
    probe.fail_after_release.add("p0")
    with patch(_LIMIT, 1, create=True):
        tasks = _launch(2)
        await _until(lambda: "p0" in probe.parked)
        await asyncio.sleep(0.05)
        assert probe.started == [_sha(0)]  # p1 은 p0 가 끝날 때까지 못 들어온다 / p1 waits for p0

        probe.release(0)
        await _until(lambda: "p1" in probe.parked)
        assert tasks[0].done() and tasks[0].exception() is None
        probe.release(1)
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)

    assert probe.finished == [_sha(1)]
    assert probe.max_inside == 1


async def test_body_never_waits_for_a_slot_it_already_holds(probe):
    """상한 1 에서도 파이프라인 하나는 끝난다 — 본문 안에서 같은 슬롯을 다시 잡으면 여기서 멈춘다.

    With a limit of 1 a single pipeline still completes — re-acquiring inside the body would hang.
    Then a second one completes too, so the slot came back.
    """
    probe.release_all()
    with patch(_LIMIT, 1, create=True):
        await asyncio.wait_for(pipeline.run_analysis_pipeline("push", _push(0)), timeout=3)
        await asyncio.wait_for(pipeline.run_analysis_pipeline("push", _push(1)), timeout=3)
    assert probe.finished == [_sha(0), _sha(1)]


async def test_only_waiting_pipelines_log_queued_with_the_waiter_count(probe, caplog):
    """기다려야 하는 파이프라인만 INFO `pipeline queued` 를 남기고, 대기 수가 1·2 로 오른다.

    Only pipelines that must wait log INFO `pipeline queued`, with the waiter count rising 1, 2.
    """
    caplog.set_level(logging.INFO, logger="src.worker.pipeline")
    with patch(_LIMIT, 1, create=True):
        tasks = _launch(3)
        await _until(lambda: len(probe.parked) >= 1)
        await asyncio.sleep(0.05)
        queued = [r for r in caplog.records if r.getMessage().startswith("pipeline queued")]
        assert [r.levelno for r in queued] == [logging.INFO, logging.INFO]
        assert [r.args[0] for r in queued] == [1, 2]  # 대기 수 / waiter count
        probe.release_all()
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)
    queued = [r for r in caplog.records if r.getMessage().startswith("pipeline queued")]
    assert len(queued) == 2  # 첫 파이프라인은 기다리지 않았다 / the first one never waited


def test_cap_holds_across_event_loops(probe):
    """루프가 바뀌어도(테스트마다 새 루프 · 재기동) 상한이 유지되고 '다른 루프에 묶인' 오류가 없다.

    The cap still holds on a fresh event loop — no "bound to a different event loop" error.
    """

    async def _scenario(offset: int) -> None:
        probe.release_all()
        tasks = [
            asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(offset + i)))
            for i in range(3)
        ]
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=3)

    with patch(_LIMIT, 1, create=True):
        asyncio.run(_scenario(0))
        asyncio.run(_scenario(10))

    assert probe.max_inside == 1
    assert len(probe.finished) == 6


async def test_slot_is_returned_when_the_dequeued_log_raises(probe):
    """대기 끝 로그가 예외를 내도 슬롯이 새지 않는다 — 새면 세 번째 파이프라인이 영영 못 들어온다.

    A raising dequeued log must not leak the permit — otherwise the third pipeline never enters.
    """
    real_info = pipeline.logger.info

    def _info(msg, *args, **kw):
        if msg.startswith("pipeline dequeued"):
            raise RuntimeError("simulated logging failure")
        return real_info(msg, *args, **kw)

    probe.release_all()
    with patch(_LIMIT, 1, create=True), patch.object(pipeline.logger, "info", side_effect=_info):
        tasks = _launch(3)
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=3)

    # 첫 번째는 기다리지 않아 끝까지 돌고, 기다린 둘은 로그 예외로 끝나되 슬롯을 돌려준다.
    # The first never waited and completes; the two waiters end on the log error but free the slot.
    assert results[0] is None
    assert probe.finished == [_sha(0)]
    assert [type(r) for r in results[1:]] == [RuntimeError, RuntimeError]
