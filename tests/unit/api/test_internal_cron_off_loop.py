"""내부 cron HTTP 엔드포인트는 세션 만들기 · 닫기와 동기 작업을 루프 밖에서 한다 (회고 원장 L17 P2-34).

The internal cron HTTP endpoints create and close their session, and run sync work, off the event loop.

인앱 스케줄러는 #1727 에서 세션 만들기 · 닫기(운영에서 연결 반납 = ROLLBACK 왕복)를 워커 스레드로 옮겼지만, 같은 작업의
HTTP 쌍둥이는 그것을 루프에서 했고 retention-sweep 은 동기 작업 전체를 루프에서 돌렸다. 계기 — 앱을 이 테스트의 루프에서
`httpx.ASGITransport` 로 돌리고, 세션 팩토리 · `close()` · 서비스가 불린 스레드를 적는다. async 서비스는 루프에서 await
되므로 루프 스레드로 적힌다 — 계기가 두 스레드를 가른다는 양성 대조다.
Instrument: the app runs on this test's loop; the session factory, close() and the service record their thread.
Async services are awaited on the loop and record it — the positive control.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import threading
from types import SimpleNamespace

import httpx
import pytest

from src.api import internal_cron
from src.main import app

_HEADER_VALUE = "cron-off-loop-test"

# 세션을 여는 엔드포인트 → (서비스 이름, 동기 함수인가, 가짜 반환값). db-heartbeat 는 세션을 열지 않는다.
# Session-opening endpoints → (service name, is it sync, fake return). db-heartbeat opens no session.
_ENDPOINTS = {
    "/api/internal/cron/weekly": ("run_weekly_reports", False, 0),
    "/api/internal/cron/trend": ("run_trend_check", False, 0),
    "/api/internal/cron/scan-security": ("scan_all_repos", False, {}),
    "/api/internal/cron/retry-pending-merges": ("process_pending_retries", False, {}),
    "/api/internal/cron/sweep-orphans": ("sweep_analysis_attempts", False, 0),
    "/api/internal/cron/retention-sweep": ("run_retention_sweep", True, {}),
}


@pytest.fixture()
def world(monkeypatch):
    h = SimpleNamespace(events=[], loop_thread=threading.current_thread())

    class _Session:
        def close(self) -> None:
            h.events.append(("close", threading.current_thread()))

    def factory() -> _Session:
        h.events.append(("open", threading.current_thread()))
        return _Session()

    monkeypatch.setattr(internal_cron, "SessionLocal", factory)
    monkeypatch.setattr("src.config.settings.internal_cron_api_key", _HEADER_VALUE)
    return h


async def _post(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        return await ac.post(path, headers={"X-API-Key": _HEADER_VALUE})


def test_every_session_endpoint_is_measured():
    """라우터의 엔드포인트가 늘면 이 시험도 그것을 재야 한다 — 목록 밖 엔드포인트가 조용히 빠지지 않게."""
    paths = {route.path for route in internal_cron.router.routes}
    # db-heartbeat · sync-claude-models 는 세션을 직접 열지 않는다 — 모델 동기화는 refresh_catalog 가 워커 스레드에서
    # 연다(tests/unit/services/test_model_catalog_service.py::test_refresh_reads_the_database_off_the_event_loop).
    # Neither opens a session itself; the model sync opens its sessions in a worker thread (measured there).
    unmeasured = {"/api/internal/cron/db-heartbeat", "/api/internal/cron/sync-claude-models"}
    assert paths - unmeasured == set(_ENDPOINTS), paths


@pytest.mark.parametrize("path", sorted(_ENDPOINTS))
async def test_cron_endpoint_keeps_its_session_and_sync_work_off_the_loop(world, monkeypatch, path):
    """🔴 수정 전 — 여섯 엔드포인트 모두 세션 만들기 · 닫기가 루프 스레드였고 retention-sweep 은 작업까지 루프였다."""
    name, sync, value = _ENDPOINTS[path]
    if sync:
        def fake(_db, **_kwargs):
            world.events.append(("service", threading.current_thread()))
            return value
    else:
        async def fake(_db, **_kwargs):
            world.events.append(("service", threading.current_thread()))
            return value
    monkeypatch.setattr(internal_cron, name, fake)

    resp = await _post(path)

    assert resp.status_code == 200, resp.text
    assert [kind for kind, _ in world.events] == ["open", "service", "close"], world.events
    thread = dict(world.events)
    assert thread["open"] is not world.loop_thread, "세션을 루프 스레드에서 만들었다"
    assert thread["close"] is not world.loop_thread, "세션을 루프 스레드에서 닫았다(연결 반납 왕복)"
    if sync:
        assert thread["service"] is not world.loop_thread, "동기 작업을 루프 스레드에서 돌렸다"
    else:
        # 양성 대조 — 루프에서 await 된 async 서비스는 루프 스레드로 적힌다.
        # Positive control: the async service, awaited on the loop, records the loop thread.
        assert thread["service"] is world.loop_thread
