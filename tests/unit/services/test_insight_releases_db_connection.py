"""인사이트 페이지는 Claude 를 기다리는 동안 DB 풀 연결을 쥐지 않는다 (#1697).

두 인사이트 경로(`insight_narrative` · `repo_insight_narrative`)는 요청 세션으로 KPI 를 읽은 뒤
Claude 응답을 **이벤트 루프 위에서** 기다린다. 읽기 트랜잭션이 열린 채면 풀 연결 하나가
최대 기한(45s) 동안 점유된다. 풀(5+10)이 다 차면 다음 요청의 동기 체크아웃이 `pool_timeout`
만큼 **루프 자체를** 멈춘다 — 그동안 연결을 쥔 쪽도 재개하지 못해 풀어 주지 못하고,
`asyncio.timeout` 기한도 발화하지 못한다. 이 파일의 T5 가 그 동결을 막는 가드다.

계기 — 실제 SQLite 파일 + `QueuePool` + 실제 `Session`. 엔진의 `after_cursor_execute` 가
쿼리마다 `pool.checkedout()` 을 적고(양성 대조: 연결을 쥔 순간을 이 계기가 «볼 수 있다»),
가짜 `messages.create` 가 await 시점의 `(checkedout, in_transaction)` 을 적는다.

Insight pages must not hold a pooled DB connection while awaiting Claude: a held read
transaction on every cache miss can exhaust the pool, and a sync checkout wait then freezes
the event loop itself. Real SQLite file + QueuePool + real Session.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import anthropic
import httpx
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.database import Base
from src.models.analysis import Analysis
from src.models.claude_api_call import ClaudeApiCall
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.repository import Repository
from src.models.user import User
from src.repositories import insight_narrative_cache_repo
from src.services import dashboard_service, repo_insight_service
from src.services.repo_insight_service import repo_kpi, repo_recurring_issues

_OK_CARDS = (
    '{"positive_highlights": ["p"], "focus_areas": ["f"], '
    '"key_metrics": [{"label": "l", "value": "1", "delta": "0"}], "next_actions": ["n"]}'
)
_OK_REPO = '{"text": "좋은 리포다"}'
# 대시보드 KPI 가 읽는 테이블까지 등록돼야 한다 — 튜플을 **읽어** import 부작용 소실을 loud-fail 한다.
# Tables the dashboard KPIs read must be registered; reading the tuple loud-fails a lost import.
_TABLES = (Analysis, ClaudeApiCall, InsightNarrativeCache, Repository, User)


# ─── 계기 ───
# ─── Instrument ───


@pytest.fixture
def world(tmp_path, monkeypatch):
    """실제 파일 SQLite(QueuePool) + 시드 + 가짜 Claude 클라이언트 + 연결 기록기.

    Real file SQLite (QueuePool), seed rows, a fake Claude client and a connection recorder.
    """
    assert all(m.__tablename__ in Base.metadata.tables for m in _TABLES)
    engine = create_engine(f"sqlite:///{tmp_path / 'insight.db'}")
    Base.metadata.create_all(engine)
    # 운영 SessionLocal 과 같게 autoflush=False — 켜면 KPI 쿼리가 미완료 쓰기를 flush 해 가드가 못 본다.
    # autoflush=False like production SessionLocal; with it on, the KPI queries flush pending writes.
    make = sessionmaker(bind=engine, autoflush=False)
    with make() as s:
        user = User(github_id=7, github_login="u", email="u@x.com", display_name="U")
        s.add(user)
        s.flush()
        repo = Repository(full_name="o/r", user_id=user.id)
        s.add(repo)
        s.flush()
        naive_now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(3):
            s.add(Analysis(repo_id=repo.id, commit_sha=f"sha{i}", score=80, grade="B",
                           result={"issues": []}, created_at=naive_now - timedelta(days=1)))
        s.commit()
        user_id, repo_id = user.id, repo.id

    h = SimpleNamespace(timeline=[], create_calls=0, ctor_calls=0, reply=None, close=AsyncMock(),
                        engine=engine, make=make, user_id=user_id, repo_id=repo_id, db=None)

    @event.listens_for(engine, "after_cursor_execute")
    def _on_sql(*_a, **_k):
        h.timeline.append(("sql", engine.pool.checkedout()))

    async def create(**_kwargs):
        h.create_calls += 1
        h.timeline.append(("await", engine.pool.checkedout(), h.db.in_transaction()))
        if h.reply is None:
            raise anthropic.APIConnectionError(
                request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
        return h.reply

    def ctor(*_a, **_k):
        h.ctor_calls += 1
        return SimpleNamespace(messages=SimpleNamespace(create=create), close=h.close)

    monkeypatch.setattr(anthropic, "AsyncAnthropic", ctor)
    monkeypatch.delenv("INSIGHT_DISABLED", raising=False)
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test")
    # 비용 행은 별도 엔진으로 간다 — 여기선 기록만.
    # Cost rows go to another engine; record only.
    monkeypatch.setattr(dashboard_service, "log_claude_api_call", MagicMock())
    monkeypatch.setattr(repo_insight_service, "log_claude_api_call", MagicMock())
    yield h
    engine.dispose()


def _text_response(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(input_tokens=10, output_tokens=5,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0)
    return resp


async def _call(h, db, site, *, refresh=False):
    """라우트와 같은 순서 — 요청 세션으로 KPI 를 읽고 나서 내러티브를 부른다.
    Same order as the routes: KPIs read on the request session, then the narrative.
    """
    h.db = db
    if site == "dashboard":
        return await dashboard_service.insight_narrative(
            db, 7, api_key="sk-test", user_id=h.user_id, refresh=refresh)
    kpi = repo_kpi(db, h.repo_id, 30)
    recurring = repo_recurring_issues(db, h.repo_id, 30)
    return await repo_insight_service.repo_insight_narrative(
        db, h.repo_id, 30, repo_full_name="o/r", kpi=kpi, recurring=recurring,
        user_id=h.user_id, refresh=refresh)


def _cache_rows(h):
    with h.make() as s:
        return list(s.scalars(select(InsightNarrativeCache)
                              .where(InsightNarrativeCache.user_id == h.user_id)).all())


def _await_entry(h):
    awaits = [e for e in h.timeline if e[0] == "await"]
    assert len(awaits) == 1, h.timeline
    return awaits[0], h.timeline.index(awaits[0])


# ─── T5: await 동안 연결을 쥐지 않는다 ───
# ─── T5: no connection held across the await ───


@pytest.mark.asyncio
@pytest.mark.parametrize("site, refresh", [
    ("dashboard", False), ("dashboard", True), ("repo", False),
    # 수정 전에도 초록인 대조군 — invalidate_repo 가 커밋한 뒤 쿼리가 없다(계기가 «해제» 를 본다).
    # Control, green before the fix too: the recorder can observe a released connection.
    ("repo", True),
], ids=["dashboard-refresh0", "dashboard-refresh1", "repo-refresh0", "repo-refresh1"])
async def test_no_pooled_connection_held_while_awaiting_claude(world, site, refresh):
    """🔴 수정 전 실측 — dashboard 두 경로와 repo refresh=0 이 `(1, True)`: 연결을 쥔 채 기다렸다."""
    with world.make() as db:
        out = await _call(world, db, site, refresh=refresh)

    assert world.create_calls == 1
    entry, idx = _await_entry(world)
    # 양성 대조 — await 전에 실제 SELECT 가 연결을 쥐었고 계기가 그것을 1 로 봤다.
    # Positive control: a real SELECT held the connection before the await and the recorder saw 1.
    assert ("sql", 1) in world.timeline[:idx], f"계기가 쥔 연결을 한 번도 못 봤다(공허): {world.timeline}"
    assert entry[1:] == (0, False), f"Claude 를 기다리는 동안 연결·트랜잭션을 쥐었다: {entry}"
    assert out["status"] == "api_error"
    # 커밋 뒤의 쓰기가 여전히 된다 — 새 세션으로 읽는다.
    # Writes after the commit still land; read them on a fresh session.
    rows = _cache_rows(world)
    assert [r.error_count for r in rows] == [1], rows


# ─── T6: 성공 응답은 여전히 캐시된다 ───
# ─── T6: success still caches ───


@pytest.mark.asyncio
@pytest.mark.parametrize("site", ["dashboard", "repo"])
async def test_success_still_caches_after_release(world, site):
    """성공은 캐시되고, 요청 세션에 이미 올린 ORM 객체는 호출 뒤에도 붙어 있고 읽힌다.

    🔴 해제를 `close()` 로 하면 객체가 세션에서 떨어진다(`repo in db` 가 거짓). 템플릿의 `repo.*` 가
    DetachedInstanceError 가 되는 것은 캐시 무효화 커밋이 객체를 만료시키는 refresh=1 경로다.
    Success is cached, and ORM objects already loaded on the request session stay attached
    and readable afterwards. A `close()` release detaches them (`repo in db` is False); the
    template's `repo.*` raises DetachedInstanceError on the refresh=1 path, where the cache
    invalidation commit has expired the object.
    """
    world.reply = _text_response(_OK_CARDS if site == "dashboard" else _OK_REPO)
    with world.make() as db:
        # 라우트처럼 호출 전에 리포를 요청 세션으로 읽어 둔다.
        # Like the routes, load the repo on the request session before the call.
        repo = db.get(Repository, world.repo_id)
        out = await _call(world, db, site)
        assert repo in db, "해제가 세션에서 객체를 떼어 냈다"
        assert repo.full_name == "o/r"
    assert out["status"] == "success"

    with world.make() as s:
        if site == "dashboard":
            cached = insight_narrative_cache_repo.get_fresh(s, user_id=world.user_id, days=7)
        else:
            cached = insight_narrative_cache_repo.get_fresh_repo(
                s, user_id=world.user_id, repo_id=world.repo_id, days=30)
    assert cached is not None and cached["status"] == "success"


# ─── 커밋 계약: 호출부의 미완료 쓰기를 몰래 커밋하지 않는다 ───
# ─── Commit contract: never commit a caller's pending writes ───


def _plant_new(_h, db):
    """새 행을 add 만 해 둔다(flush 전).
    Add a row, unflushed."""
    db.add(User(github_id=99, github_login="planted", email="p@x.com", display_name="P"))

    def persisted(s):
        return s.scalar(select(User).where(User.github_login == "planted")) is not None
    return persisted


def _plant_dirty(h, db):
    """시드 행을 고쳐 둔다(flush 전).
    Modify a seeded row, unflushed."""
    db.get(User, h.user_id).display_name = "PLANTED"

    def persisted(s):
        return s.get(User, h.user_id).display_name == "PLANTED"
    return persisted


def _plant_deleted(_h, db):
    """시드 행을 지워 둔다(flush 전).
    Delete a seeded row, unflushed."""
    db.delete(db.scalar(select(Analysis).where(Analysis.commit_sha == "sha0")))

    def persisted(s):
        return s.scalar(select(Analysis).where(Analysis.commit_sha == "sha0")) is None
    return persisted


@pytest.mark.asyncio
@pytest.mark.parametrize("plant", [_plant_new, _plant_dirty, _plant_deleted],
                         ids=["new", "dirty", "deleted"])
@pytest.mark.parametrize("site", ["dashboard", "repo"])
async def test_pending_caller_write_is_refused_not_committed(world, site, plant):
    """🔴 심은 반례 — 호출부가 세션에 쓰기(new·dirty·deleted)를 남겨 둔 채 부르면 거부한다.

    log-and-skip 이 아니라 raise 인 이유: 건너뛰어도 뒤따르는 캐시 쓰기(`record_error`·`upsert`)
    가 스스로 커밋하므로 그 쓰기는 결국 커밋된다. 막는 길은 멈추는 것뿐이다.
    가드는 클라이언트 생성보다 앞이어야 한다 — 뒤면 거부 경로에서 httpx 풀이 닫히지 않는다.
    Each pending kind (new, dirty, deleted) is refused before the paid call and before the
    client exists; a bare commit or skip would commit it via the later cache writes.
    """
    with world.make() as db:
        persisted = plant(world, db)
        with pytest.raises(RuntimeError, match="pending"):
            await _call(world, db, site)
        db.rollback()

    assert world.create_calls == 0, "거부 전에 유료 호출을 했다"
    assert world.ctor_calls == 0, "거부 전에 클라이언트를 만들었다(거부 경로에서 닫히지 않는다)"
    with world.make() as s:
        assert not persisted(s), "호출부의 미완료 쓰기가 커밋됐다"


# ─── T7: 바깥 취소에도 클라이언트를 닫는다 ───
# ─── T7: outer cancel still closes the client ───


@pytest.mark.asyncio
@pytest.mark.parametrize("site", [
    "dashboard",
    # 대조군 — repo 는 이미 finally 에서 닫는다.
    # Control: repo already closes in finally.
    "repo",
])
async def test_outer_cancel_still_closes_client(world, monkeypatch, site):
    """🔴 수정 전 dashboard 는 `aclose` 가 finally 밖이라 취소(`CancelledError`)가 그것을 건너뛰었다."""
    entered, never = asyncio.Event(), asyncio.Event()

    async def hang(**_kwargs):
        entered.set()
        await never.wait()

    def ctor(*_a, **_k):
        return SimpleNamespace(messages=SimpleNamespace(create=hang), close=world.close)

    monkeypatch.setattr(anthropic, "AsyncAnthropic", ctor)
    with world.make() as db:
        task = asyncio.ensure_future(_call(world, db, site))
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=5)

    world.close.assert_awaited_once()
