"""인사이트 두 페이지의 동기 DB 작업은 이벤트 루프 스레드에서 돌지 않는다 (#1701).

Neither insight page runs its synchronous DB work on the event-loop thread (#1701).

운영(앱 us-east4 ↔ DB ap-southeast-2, 왕복 ≈ 0.21 s)에서 `/dashboard?mode=insight` 캐시 miss 는
Claude 호출 앞 ~8.6 s · 뒤 ~3.4 s 를 **루프 위에서** 동기로 돌렸다. 그동안 같은 프로세스의 다른
요청(웹훅 202 포함)은 한 바이트도 쓰지 못한다. overview·security·usage 는 이미 `run_in_threadpool` 이다.
In production the insight cache miss ran ~8.6 s before and ~3.4 s after the Claude call synchronously
on the loop, starving every other request in the process (webhook 202s included).

계기 — 앱을 `httpx.ASGITransport` 로 **이 테스트의 루프에서** 돌린다. 그래서 루프 스레드 =
테스트 코루틴의 스레드다. 동기 DB 이름마다 호출 스레드를 적고(원래 함수는 그대로 부른다),
가짜 `messages.create`(루프에서 await 된다)가 루프 스레드를 적는다 — 계기가 두 스레드를
구별할 수 있다는 양성 대조다. 실제 SQLite(StaticPool) 로 캐시·KPI 가 진짜로 돈다.
Instrument: the app runs on this test's loop through ASGITransport, so the loop thread is the test
coroutine's thread. Each sync DB name records its calling thread (the real function still runs);
the fake `messages.create`, awaited on the loop, records the loop thread as the positive control.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from functools import wraps
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import Base
from src.main import app
from src.models.analysis import Analysis
from src.models.claude_api_call import ClaudeApiCall
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.repositories import insight_narrative_cache_repo
from src.services import dashboard_service, repo_insight_service
from src.ui.routes import dashboard as dashboard_route
from src.ui.routes import repo_insights as repo_insights_route

# KPI 가 읽는 테이블까지 등록돼야 한다 — 튜플을 **읽어** import 부작용 소실을 loud-fail 한다.
# Tables the KPIs read must be registered; reading the tuple loud-fails a lost import.
_TABLE_MODELS = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_REPO = "offloop-owner/offloop-repo"
_OK_CARDS = json.dumps({
    "positive_highlights": ["잘했다"], "focus_areas": ["볼 것"],
    "key_metrics": [{"label": "평균", "value": "80", "delta": "+1"}], "next_actions": ["다음"],
})
_OK_REPO = json.dumps({"text": "진단 서술"})

# 페이지마다 동기 DB 를 하는 이름 — (모듈, 속성). 라우트·서비스가 호출 시점에 이 속성을 찾는다.
# Per page, the names that do sync DB work; routes and services look these up at call time.
_SYNC_NAMES = {
    "dashboard": [
        (dashboard_service, "dashboard_kpi"), (dashboard_service, "dashboard_trend"),
        (dashboard_service, "frequent_issues_v2"), (dashboard_service, "auto_merge_kpi"),
        (dashboard_service, "release_session_before_claude"),
        (insight_narrative_cache_repo, "get_fresh"), (insight_narrative_cache_repo, "recent_error"),
        (insight_narrative_cache_repo, "upsert"), (insight_narrative_cache_repo, "record_error"),
        (insight_narrative_cache_repo, "invalidate"),
    ],
    "repo": [
        (repo_insights_route, "_find_repo"), (repo_insights_route, "repo_kpi"),
        (repo_insights_route, "repo_recurring_issues"), (repo_insights_route, "repo_problem_files"),
        (repo_insights_route, "repo_ai_suggestions"), (repo_insights_route, "repo_category_breakdown"),
        (repo_insight_service, "release_session_before_claude"),
        (insight_narrative_cache_repo, "get_fresh_repo"),
        (insight_narrative_cache_repo, "recent_error_repo"),
        (insight_narrative_cache_repo, "upsert_repo"), (insight_narrative_cache_repo, "record_error_repo"),
        (insight_narrative_cache_repo, "invalidate_repo"),
    ],
}
# 비용 행 기록(`_persist_cost` → WorkerSessionLocal INSERT)도 동기 DB 다 — 가짜로 바꿔 스레드만 적는다.
# Cost-row persistence is sync DB too; replaced by a recorder that only notes the thread.
_COST_LOGGERS = {"dashboard": dashboard_service, "repo": repo_insight_service}

_KPI_NAMES = {
    "dashboard": {"dashboard_kpi", "dashboard_trend", "frequent_issues_v2", "auto_merge_kpi"},
    "repo": {"_find_repo", "repo_kpi", "repo_recurring_issues", "repo_problem_files",
             "repo_ai_suggestions", "repo_category_breakdown"},
}
# 시나리오마다 «반드시 불렸어야 하는» 이름 — 안 불렸으면 «루프 밖» 단언이 공허하다.
# Names that must have run per scenario; otherwise the off-loop assertion is vacuous.
_EXPECTED = {
    ("dashboard", "success"): _KPI_NAMES["dashboard"] | {
        "release_session_before_claude", "get_fresh", "recent_error", "upsert", "log_claude_api_call"},
    ("dashboard", "api_error"): _KPI_NAMES["dashboard"] | {
        "release_session_before_claude", "get_fresh", "recent_error", "record_error",
        "log_claude_api_call"},
    ("dashboard", "refresh"): {"invalidate"},
    ("repo", "success"): _KPI_NAMES["repo"] | {
        "release_session_before_claude", "get_fresh_repo", "recent_error_repo", "upsert_repo",
        "log_claude_api_call"},
    ("repo", "api_error"): _KPI_NAMES["repo"] | {
        "release_session_before_claude", "get_fresh_repo", "recent_error_repo", "record_error_repo",
        "log_claude_api_call"},
    ("repo", "refresh"): {"_find_repo", "invalidate_repo"},
}


def _url(page: str, *, days: int, refresh: bool = False) -> str:
    tail = "&refresh=1" if refresh else ""
    if page == "dashboard":
        return f"/dashboard?mode=insight&days={days}{tail}"
    return f"/repos/{_REPO}/insights?days={days}{tail}"


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def db():
    """스레드 사이에서 넘겨 쓸 수 있는 인메모리 SQLite — 운영 풀과 같이 «한 번에 한 스레드» 로만 쓴다.
    In-memory SQLite shareable across threads; used by one thread at a time like the production pool.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def owner(db) -> int:
    """사용자 1 + 소유 리포 1 + 창 안의 분석 3건."""
    u = User(github_id=f"ol-{uuid.uuid4().hex[:8]}", github_login="ol", email="ol@x.com",
             display_name="OL")
    db.add(u)
    db.commit()
    r = Repository(full_name=_REPO, user_id=u.id)
    db.add(r)
    db.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i, score in enumerate((80, 85, 72)):
        db.add(Analysis(repo_id=r.id, commit_sha=f"ol{uuid.uuid4().hex}", score=score, grade="B",
                        result={"issues": []}, created_at=now - timedelta(hours=i + 1)))
    db.commit()
    return u.id


@pytest.fixture()
def world(db, owner, monkeypatch):
    """로그인·세션·가짜 Claude·스레드 기록기를 묶는다. 앱은 테스트 루프에서 ASGITransport 로 돈다.
    Wires login, session, a fake Claude and the thread recorder; the app runs on the test loop.
    """
    h = SimpleNamespace(calls=[], create_threads=[], sql_threads=[], reply=None,
                        loop_thread=threading.current_thread())

    # 이름 없는 SQL 도 잡는다 — 템플릿의 `repo.*` 지연 로드처럼 기록기를 거치지 않는 문장까지.
    # Also catch unnamed SQL, e.g. a lazy load from the template's `repo.*`, via the engine itself.
    def _on_sql(*_a, **_k):
        h.sql_threads.append(threading.current_thread())

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _on_sql)

    def recorder(name, fn):
        @wraps(fn)
        def wrapper(*a, **k):
            h.calls.append((name, threading.current_thread()))
            return fn(*a, **k)
        return wrapper

    for names in _SYNC_NAMES.values():
        for mod, name in names:
            monkeypatch.setattr(mod, name, recorder(name, getattr(mod, name)))
    for mod in _COST_LOGGERS.values():
        monkeypatch.setattr(mod, "log_claude_api_call",
                            recorder("log_claude_api_call", lambda *_a, **_k: None))

    async def create(**_kwargs):
        h.create_threads.append(threading.current_thread())
        if h.reply is None:
            raise anthropic.APIConnectionError(
                message="connection failed",
                request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        return h.reply

    client = SimpleNamespace(messages=SimpleNamespace(create=create))
    for mod in (dashboard_service, repo_insight_service):
        monkeypatch.setattr(mod, "new_async_anthropic", MagicMock(return_value=client))
        monkeypatch.setattr(mod, "aclose_anthropic_client", AsyncMock())
    monkeypatch.delenv("INSIGHT_DISABLED", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-test")
    # 대시보드는 의존성이 아니라 `SessionLocal()` 을 직접 연다 — 같은 세션을 닫지 않고 건넨다.
    # The dashboard opens `SessionLocal()` directly; hand it the same session without closing it.
    monkeypatch.setattr(dashboard_route, "SessionLocal", lambda: nullcontext(db))

    current = CurrentUser(id=owner, github_login="ol", email="ol@x.com", display_name="OL",
                          plaintext_token="ghp_test")
    prev = {dep: app.dependency_overrides.get(dep) for dep in (require_login, repo_insights_route._get_db)}
    app.dependency_overrides[require_login] = lambda: current
    app.dependency_overrides[repo_insights_route._get_db] = lambda: db
    yield h
    event.remove(engine, "before_cursor_execute", _on_sql)
    for dep, old in prev.items():
        if old is None:
            app.dependency_overrides.pop(dep, None)
        else:
            app.dependency_overrides[dep] = old


def _reply(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.stop_reason = "end_turn"
    resp.usage = MagicMock(input_tokens=100, output_tokens=50,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return resp


async def _get(url: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        return await ac.get(url)


# ─── 동기 DB 는 루프 스레드 밖에서 ──────────────────────────────────────────────


@pytest.mark.parametrize("outcome", ["success", "api_error", "refresh"])
@pytest.mark.parametrize("page", ["dashboard", "repo"])
async def test_sync_db_work_never_runs_on_the_event_loop_thread(world, page, outcome):
    """🔴 수정 전 실측 — 두 페이지 모두 KPI·캐시·부정 캐시·비용 기록이 루프 스레드에서 돌았다."""
    if outcome == "success":
        world.reply = _reply(_OK_CARDS if page == "dashboard" else _OK_REPO)

    r = await _get(_url(page, days=7, refresh=outcome == "refresh"))

    assert r.status_code == (303 if outcome == "refresh" else 200), r.text[:300]
    called = {name for name, _ in world.calls}
    missing = _EXPECTED[(page, outcome)] - called
    assert not missing, f"기대한 동기 호출이 없었다(단언이 공허해진다): {sorted(missing)}"
    if outcome != "refresh":
        # 양성 대조 — Claude await 는 루프 스레드에서 돌았고 계기가 그 스레드를 봤다.
        # Positive control: the Claude await ran on the loop thread and the recorder saw it.
        assert world.create_threads == [world.loop_thread]
    on_loop = sorted({name for name, t in world.calls if t is world.loop_thread})
    assert not on_loop, f"이벤트 루프 스레드에서 돈 동기 DB 작업: {on_loop}"
    assert world.sql_threads, "SQL 이 한 문장도 안 잡혔다 — 엔진 기록기가 공허하다"
    sql_on_loop = sum(t is world.loop_thread for t in world.sql_threads)
    assert not sql_on_loop, f"이벤트 루프 스레드에서 실행된 SQL {sql_on_loop}문장 / {len(world.sql_threads)}"


# ─── 느린 KPI 가 같은 루프의 다른 코루틴을 세우지 않는다 ─────────────────────────


@pytest.mark.parametrize("page, slow_target", [
    ("dashboard", (dashboard_service, "dashboard_kpi")),
    ("repo", (repo_insights_route, "repo_kpi")),
], ids=["dashboard", "repo"])
async def test_slow_kpi_helper_does_not_stall_a_concurrent_ticker(world, monkeypatch, page, slow_target):
    """🔴 KPI 헬퍼가 0.5 s 동안 동기로 막혀도 같은 루프의 10 ms 티커는 계속 돈다.

    수정 전에는 티커의 최대 간격이 막힌 시간 그대로(≥ 0.5 s)였다 — 웹훅 202 가 늦던 것과 같은 모양.
    Before the fix the ticker's largest gap equalled the stall (>= 0.5 s), the webhook-202 shape.
    """
    world.reply = _reply(_OK_CARDS if page == "dashboard" else _OK_REPO)
    # 템플릿 첫 컴파일·지연 import 를 먼저 치른다 — 측정할 요청은 다른 창(days)이라 캐시 miss 다.
    # Pay the first template compile and lazy imports first; the measured request uses another window.
    assert (await _get(_url(page, days=7))).status_code == 200

    slow = 0.5
    mod, name = slow_target
    real = getattr(mod, name)
    slow_calls = []

    def slow_helper(*a, **k):
        slow_calls.append(threading.current_thread())
        time.sleep(slow)
        return real(*a, **k)

    monkeypatch.setattr(mod, name, slow_helper)
    gaps: list[float] = []
    done = asyncio.Event()

    async def ticker():
        last = time.perf_counter()
        while not done.is_set():
            await asyncio.sleep(0.01)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    tick = asyncio.create_task(ticker())
    await asyncio.sleep(0.05)
    started = time.perf_counter()
    r = await _get(_url(page, days=14))
    elapsed = time.perf_counter() - started
    done.set()
    await tick

    assert r.status_code == 200
    # 양성 대조 — 느린 헬퍼가 실제로 불렸고 요청은 실제로 그만큼 걸렸다.
    # Positive control: the slow helper ran and the request really took that long.
    assert slow_calls, "느린 헬퍼가 불리지 않았다 — 측정이 공허하다"
    assert elapsed >= slow
    assert max(gaps) < 0.25, (
        f"티커 최대 간격 {max(gaps):.3f}s — 느린 동기 헬퍼가 루프를 {slow}s 막았다")
