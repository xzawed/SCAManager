"""Claude 모델 동기화 예약 작업 — 6시간마다 + 기동 직후 한 번, 기동을 막지 않는다 (Issue #1905 ①a Task 3).

Claude model sync job: every 6 hours plus once right after start, without blocking startup.
"""
import asyncio
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import scheduler as sched
from src.api import internal_cron
from src.config import settings
from src.database import WorkerSessionLocal

_ENABLED = SimpleNamespace(is_production=True, scheduler_disabled=False)
_CRON_KEY = "cron-key-for-tests"


def test_model_sync_job_runs_every_six_hours_and_at_start():
    by_name = {job.name: job for job in sched.JOBS}
    assert by_name["sync-claude-models"].every_seconds == 21600
    # 기동 직후에도 도는 작업은 이것 하나 / the only job that also runs right after start
    assert [job.name for job in sched.JOBS if job.run_at_start] == ["sync-claude-models"]


async def test_model_sync_runs_once_at_start_without_blocking(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    calls = []

    async def _blocked_refresh(**kwargs):
        calls.append(kwargs)
        started.set()
        await release.wait()

    monkeypatch.setattr(sched, "refresh_catalog", _blocked_refresh)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    # start() 는 동기 함수다 — 막힌 동기화를 기다리지 않고 돌아와야 기동이 이어진다.
    # start() is synchronous; it must return without waiting on the blocked sync so startup continues.
    tasks = sched.start(_ENABLED)
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert calls == [{"api_key": "test-key", "session_factory": WorkerSessionLocal}]
        # 따로 띄운 태스크가 아니라 그 job 의 루프가 첫 잠 전에 한 번 돈다 / the job loop runs once before its first sleep
        assert len(tasks) == len(sched.JOBS)
    finally:
        await sched.stop(tasks)
    assert all(task.done() for task in tasks)


async def test_model_sync_skips_without_api_key(monkeypatch):
    calls = []

    async def _refresh(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(sched, "refresh_catalog", _refresh)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    await sched._sync_claude_models()
    assert calls == []


async def test_startup_run_failure_is_logged_not_raised(monkeypatch, caplog):
    async def _boom(**_kwargs):
        raise RuntimeError("listing exploded")

    monkeypatch.setattr(sched, "refresh_catalog", _boom)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    job = {job.name: job for job in sched.JOBS}["sync-claude-models"]
    with caplog.at_level("ERROR", logger="src.scheduler"):
        await sched._run_job_once(job)
    assert "scheduler job failed: sync-claude-models" in caplog.text


def _cron_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "internal_cron_api_key", _CRON_KEY)
    app = FastAPI()
    app.include_router(internal_cron.router)
    return TestClient(app)


def test_cron_endpoint_reports_the_refresh(monkeypatch):
    calls = []

    async def _refresh(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(source="api", promoted={"haiku": "claude-haiku-5-5"}, failed={"opus": "rejected"})

    monkeypatch.setattr(internal_cron, "refresh_catalog", _refresh)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    resp = _cron_client(monkeypatch).post("/api/internal/cron/sync-claude-models", headers={"X-API-Key": _CRON_KEY})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "source": "api",
                           "promoted": {"haiku": "claude-haiku-5-5"}, "failed": {"opus": "rejected"}}
    assert calls == [{"api_key": "test-key", "session_factory": WorkerSessionLocal}]


def test_cron_endpoint_skips_without_api_key(monkeypatch):
    calls = []

    async def _refresh(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(internal_cron, "refresh_catalog", _refresh)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    resp = _cron_client(monkeypatch).post("/api/internal/cron/sync-claude-models", headers={"X-API-Key": _CRON_KEY})
    assert (resp.status_code, resp.json()["status"], calls) == (200, "skipped", [])
