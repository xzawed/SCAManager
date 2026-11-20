"""슬롯을 기다리는 파이프라인도 시작 흔적을 남긴다 — 기다리는 중 배포 · 재시작에 사라져도 고아 정리가 찾는다.

A pipeline waiting for a slot leaves its start breadcrumb too, so one lost while waiting is still found by the
orphan sweep (retro ledger L17 P2-32).

이전에는 흔적(`analysis_attempts`)을 본문 안에서만 남겨, 슬롯을 기다리던 파이프라인은 배포 · 재시작에 흔적 없이
사라졌다. 이제 기다려야 할 때 기다리기 **직전에** 남긴다(리포 행이 있으면 · 루프 밖). 본문이 시작하면 그 흔적의
시작 시각을 다시 잡아 긴 대기가 고아 판정 기준을 먹지 않게 한다. 실제 SQLite 파일 DB 에 실제 행을 쓴다.
Before, only the body wrote the breadcrumb. Now it is written right before waiting (repo row present, off the loop),
and the body restarts its clock. Real rows in a real SQLite file database.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import src.worker.pipeline as pipeline
from src.database import Base
from src.models.analysis import Analysis
from src.models.analysis_attempt import AnalysisAttempt
from src.models.repository import Repository

_LIMIT = "src.worker.pipeline.PIPELINE_MAX_CONCURRENCY"
_SHA = "c0ffee" + "0" * 33 + "1"
_KNOWN = "owner/queued"


def _push(repo_name: str, sha: str = _SHA) -> dict:
    return {"repository": {"full_name": repo_name}, "after": sha,
            "head_commit": {"id": sha, "message": "queued push"}}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """파일 SQLite(스레드마다 자기 연결) + 리포 1 + 기록기. 파이프라인의 워커 세션을 이 DB 로 돌린다."""
    engine = create_engine(f"sqlite:///{tmp_path / 'queued.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    make = sessionmaker(bind=engine)
    with make() as db:
        repo = Repository(full_name=_KNOWN)
        db.add(repo)
        db.commit()
        repo_id = repo.id
    monkeypatch.setattr(pipeline, "SessionLocal", make)

    h = SimpleNamespace(repo_id=repo_id, make=make, queued_calls=[], loop_thread=threading.current_thread())
    real = pipeline._begin_queued_attempt  # pylint: disable=protected-access

    @wraps(real)
    def recorder(*args, **kwargs):
        h.queued_calls.append(threading.current_thread())
        return real(*args, **kwargs)

    monkeypatch.setattr(pipeline, "_begin_queued_attempt", recorder)

    def attempts() -> list[tuple[int, str]]:
        with make() as db:
            return [(row.repo_id, row.commit_sha) for row in db.query(AnalysisAttempt).all()]

    h.attempts = attempts
    yield h
    engine.dispose()


async def _until(cond, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not cond():
        if time.monotonic() > deadline:
            raise AssertionError("condition not reached before timeout")
        await asyncio.sleep(0.005)


class _Holder:
    """슬롯 하나를 쥐고 놓아 줄 때까지 기다리는 태스크 — 다음 파이프라인이 기다리게 만든다."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.task: asyncio.Task | None = None

    async def _hold(self) -> None:
        async with pipeline._pipeline_slot():  # pylint: disable=protected-access
            self.entered.set()
            await self.release.wait()

    async def __aenter__(self) -> "_Holder":
        self.task = asyncio.create_task(self._hold())
        await self.entered.wait()
        return self

    async def __aexit__(self, *_exc) -> None:
        self.release.set()
        await self.task


async def test_a_pipeline_lost_while_waiting_leaves_a_trace(world):
    """🔴 본체 — 기다리는 중 취소(배포 · 재시작)돼도 흔적이 남는다. 수정 전에는 행 0개였다."""
    with patch(_LIMIT, 1, create=True):
        async with _Holder():
            waiter = asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(_KNOWN)))
            await _until(lambda: world.attempts() == [(world.repo_id, _SHA)])
            assert pipeline._current_slots().waiting == 1  # pylint: disable=protected-access
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                _ = await waiter
    assert world.attempts() == [(world.repo_id, _SHA)], "기다리다 사라진 파이프라인의 흔적이 없다"


async def test_a_first_seen_repo_waits_without_a_trace_and_without_error(world):
    """처음 보는 리포는 행이 없어 대기 전 흔적을 남기지 못한다 — 오류 없이 기다린다(본문이 등록한 뒤 남긴다)."""
    with patch(_LIMIT, 1, create=True):
        async with _Holder():
            waiter = asyncio.create_task(pipeline.run_analysis_pipeline("push", _push("owner/brand-new")))
            await _until(lambda: len(world.queued_calls) == 1)
            await asyncio.sleep(0.05)  # 흔적 쓰기가 끝날 시간 / let the write attempt finish
            assert world.attempts() == []
            assert pipeline._current_slots().waiting == 1  # pylint: disable=protected-access
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                _ = await waiter


async def test_the_queued_trace_is_written_off_the_event_loop(world):
    """대기분은 수만큼 겹친다 — 흔적 쓰기는 루프 스레드가 아닌 워커 스레드에서."""
    with patch(_LIMIT, 1, create=True):
        async with _Holder():
            waiter = asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(_KNOWN)))
            await _until(lambda: world.attempts() == [(world.repo_id, _SHA)])
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                _ = await waiter
    assert world.queued_calls and all(t is not world.loop_thread for t in world.queued_calls), world.queued_calls


async def test_a_pipeline_that_does_not_wait_leaves_the_trace_to_the_body(world):
    """빈 슬롯으로 바로 들어가면 대기 전 흔적은 없다 — 본문 시작 때 행이 아직 없어야 한다(본문이 남긴다)."""
    seen_at_body_start: list[list[tuple[int, str]]] = []

    async def body(_event, _data):
        seen_at_body_start.append(world.attempts())

    with patch(_LIMIT, 1, create=True), patch.object(pipeline, "_run_pipeline_body", body):
        await asyncio.wait_for(pipeline.run_analysis_pipeline("push", _push(_KNOWN)), timeout=5)
    assert seen_at_body_start == [[]]
    assert world.queued_calls == []


def test_the_body_restarts_the_clock_of_a_queued_trace(world):
    """본문 시작의 `_begin_attempt` 가 대기 전 흔적의 시작 시각을 지금으로 — 긴 대기가 고아 판정을 먹지 않게."""
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    with world.make() as db:
        db.add(AnalysisAttempt(repo_id=world.repo_id, commit_sha=_SHA, started_at=old))
        db.commit()

    pipeline._begin_attempt(world.repo_id, _SHA, None, "push")  # pylint: disable=protected-access

    with world.make() as db:
        started = db.query(AnalysisAttempt).one().started_at
    assert started > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1), started


async def test_the_queued_log_names_the_commit(world, caplog):
    """대기 로그에 커밋 SHA 앞 8자 — 사라진 대기분을 로그에서도 짚을 수 있게."""
    caplog.set_level(logging.INFO, logger="src.worker.pipeline")
    with patch(_LIMIT, 1, create=True):
        async with _Holder():
            waiter = asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(_KNOWN)))
            await _until(lambda: world.attempts() == [(world.repo_id, _SHA)])
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                _ = await waiter
    queued = [r for r in caplog.records if r.getMessage().startswith("pipeline queued")]
    assert [r.args[2] for r in queued] == [_SHA[:8]]


def _slow_note_for(world, monkeypatch, slow_sha: str, seconds: float) -> None:
    """한 SHA 의 대기 전 흔적 쓰기만 느리게 — 워커 스레드에서 잠든 뒤 진짜 쓰기를 한다."""
    real = pipeline._begin_queued_attempt  # pylint: disable=protected-access

    def slow(repo_name, commit_sha, pr_number, event):
        if commit_sha == slow_sha:
            time.sleep(seconds)
        return real(repo_name, commit_sha, pr_number, event)

    monkeypatch.setattr(pipeline, "_begin_queued_attempt", slow)


async def test_a_slow_queued_note_does_not_reorder_the_queue(world, monkeypatch):
    """🔴 먼저 온 B 의 흔적 쓰기가 느려도 B 가 C 보다 먼저 들어간다 — 쓰기를 기다렸다 줄을 서면 C 가 앞선다."""
    sha_b, sha_c = "b" * 40, "c" * 40
    _slow_note_for(world, monkeypatch, sha_b, 0.4)
    entered: list[str] = []

    async def body(_event, data):
        entered.append(data["after"])

    with patch(_LIMIT, 1, create=True), patch.object(pipeline, "_run_pipeline_body", body):
        async with _Holder() as holder:
            b = asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(_KNOWN, sha_b)))
            await _until(lambda: pipeline._current_slots().waiting == 1)  # pylint: disable=protected-access
            c = asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(_KNOWN, sha_c)))
            await _until(lambda: (world.repo_id, sha_c) in world.attempts())  # C 의 쓰기만 끝났다
            assert (world.repo_id, sha_b) not in world.attempts()
            holder.release.set()
        await asyncio.wait_for(asyncio.gather(b, c), timeout=5)
    assert entered == [sha_b, sha_c]


async def test_the_body_starts_only_after_its_queued_note_is_written(world, monkeypatch):
    """슬롯을 먼저 잡아도 본문은 대기 전 흔적 쓰기가 끝난 뒤 — 늦게 끝난 흔적이 정상 종료 뒤 고아로 남지 않게."""
    _slow_note_for(world, monkeypatch, _SHA, 0.3)
    seen_at_body_start: list[list[tuple[int, str]]] = []

    async def body(_event, _data):
        seen_at_body_start.append(world.attempts())

    with patch(_LIMIT, 1, create=True), patch.object(pipeline, "_run_pipeline_body", body):
        async with _Holder() as holder:
            waiter = asyncio.create_task(pipeline.run_analysis_pipeline("push", _push(_KNOWN)))
            await _until(lambda: pipeline._current_slots().waiting == 1)  # pylint: disable=protected-access
            holder.release.set()  # 흔적 쓰기(0.3 s)가 끝나기 전에 슬롯이 빈다
        await asyncio.wait_for(waiter, timeout=5)
    assert seen_at_body_start == [[(world.repo_id, _SHA)]]


def _pr(repo_name: str, number: int, sha: str = _SHA) -> dict:
    return {"repository": {"full_name": repo_name}, "number": number,
            "pull_request": {"head": {"sha": sha, "ref": "feature"}, "title": "queued pr"}}


def _seed_analysis(world, *, result: dict | None) -> None:
    """이 커밋의 분석이 이미 저장돼 있다 — 줄을 섰던 이벤트의 본문은 «이미 분석함» 으로 끝난다.

    The commit is already analyzed, so the queued event's body ends on the dedup path (a PR event that
    arrives after its push finished).
    """
    with world.make() as db:
        db.add(Analysis(repo_id=world.repo_id, commit_sha=_SHA, score=80, grade="B", result=result))
        db.commit()


async def _queue_then_run(world, event: str, payload: dict) -> None:
    """슬롯을 쥔 채 이벤트를 줄 세워 대기 전 흔적이 써진 것을 본 뒤, 슬롯을 놓고 진짜 본문까지 끝낸다."""
    with patch(_LIMIT, 1, create=True):
        async with _Holder() as holder:
            waiter = asyncio.create_task(pipeline.run_analysis_pipeline(event, payload))
            await _until(lambda: world.attempts() == [(world.repo_id, _SHA)])
            holder.release.set()
        await asyncio.wait_for(waiter, timeout=5)


@pytest.mark.parametrize(
    ("event", "payload"),
    [("push", _push(_KNOWN)), ("pull_request", _pr(_KNOWN, 7))],
    ids=["push", "pull_request"],
)
async def test_a_queued_event_for_an_analyzed_commit_leaves_no_trace(world, event, payload):
    """🔴 본체(회고 원장 R-19) — 줄을 섰던 이벤트가 «이미 분석함» 으로 끝나면 대기 전 흔적도 지운다.

    지우지 않으면 30분 뒤 고아 정리가 잃은 것 없는 분석을 «사라진 분석» 으로 알린다. 기존 시험은 본문을
    바꿔 끼워 이 출구를 한 번도 돌지 않았다 — 여기서는 진짜 본문을 끝까지 돌린다.
    A queued event that ends on the dedup path clears its before-wait breadcrumb; otherwise the orphan sweep
    reports a lost analysis 30 minutes later. Runs the real body (the older tests swapped it out).
    """
    _seed_analysis(world, result=None)
    await _queue_then_run(world, event, payload)
    assert world.attempts() == [], "이미 분석된 커밋인데 대기 전 흔적이 남았다"


async def test_the_trace_is_cleared_before_the_regate(world, monkeypatch):
    """재게이트보다 먼저 지운다 — 분석은 이미 저장돼 있어 재게이트 실패는 소실이 아니다(알림과 같은 원칙).

    Cleared before the regate: the analysis is persisted, so a regate failure is not a loss (as for notify).
    """
    _seed_analysis(world, result={"source": "webhook"})
    seen_at_gate: list[list[tuple[int, str]]] = []

    async def gate(**_kwargs) -> None:
        seen_at_gate.append(world.attempts())

    monkeypatch.setattr(pipeline, "run_gate_check", gate)
    await _queue_then_run(world, "pull_request", _pr(_KNOWN, 7))
    assert seen_at_gate == [[]], seen_at_gate
    assert world.attempts() == []
