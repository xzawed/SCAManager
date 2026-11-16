"""대시보드 repos 모드 «고른 리포» 레포트의 동기 DB 는 이벤트 루프 스레드에서 돌지 않는다 (회고 원장 L17 P2-6 · P2-33).

The selected-repo report in dashboard repos mode runs none of its sync DB work on the event-loop thread.

요약(`_build_repo_summary`)은 이미 `run_in_threadpool` 이었지만, 리포를 고르면 리포 조회 + 집계 6개가 라우트 안에서
**루프 위로** 돌았다 — 그동안 같은 프로세스의 다른 요청(웹훅 202 포함)은 한 바이트도 쓰지 못한다.
계기 — 앱을 `httpx.ASGITransport` 로 이 테스트의 루프에서 돌려 루프 스레드 = 테스트 코루틴의 스레드다. 엔진의
`before_cursor_execute` 가 문장마다 실행 스레드를 적는다(이름 없는 문장까지). 양성 대조로 루프 스레드에서 문장 하나를
먼저 돌려 계기가 루프 스레드를 «루프» 로 적는지 본다.
Instrument: the app runs on this test's loop via ASGITransport; the engine records the thread of every statement.
A statement run on the loop first is the positive control.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import threading
import uuid
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.auth.session import CurrentUser, require_login
from src.database import Base
from src.main import app
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.ui.routes import dashboard as dashboard_route

_REPO = "offloop-owner/repos-report"


@pytest.fixture()
def db():
    """스레드 사이에서 넘겨 쓸 수 있는 인메모리 SQLite — 운영 풀처럼 «한 번에 한 스레드» 로만 쓴다."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def world(db, monkeypatch):
    """사용자 1 · 소유 리포 1 · 창 안의 분석 3건 + 로그인 + 문장별 스레드 기록기."""
    u = User(github_id=f"rr-{uuid.uuid4().hex[:8]}", github_login="rr", email="rr@x.com", display_name="RR")
    db.add(u)
    db.commit()
    r = Repository(full_name=_REPO, user_id=u.id)
    db.add(r)
    db.commit()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i, score in enumerate((80, 85, 72)):
        db.add(Analysis(repo_id=r.id, commit_sha=f"rr{uuid.uuid4().hex}", score=score, grade="B",
                        result={"issues": [{"message": "same", "category": "code_quality"}]},
                        score_unreliable=False, created_at=now - timedelta(hours=i + 1)))
    db.commit()

    h = SimpleNamespace(sql_threads=[], loop_thread=threading.current_thread())

    def _on_sql(*_a, **_k):
        h.sql_threads.append(threading.current_thread())

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", _on_sql)
    # 대시보드는 의존성이 아니라 `SessionLocal()` 을 직접 연다 — 같은 세션을 닫지 않고 건넨다.
    # The dashboard opens `SessionLocal()` directly; hand it the same session without closing it.
    monkeypatch.setattr(dashboard_route, "SessionLocal", lambda: nullcontext(db))
    current = CurrentUser(id=u.id, github_login="rr", email="rr@x.com", display_name="RR",
                          plaintext_token="ghp_test")
    prev = app.dependency_overrides.get(require_login)
    app.dependency_overrides[require_login] = lambda: current
    yield h
    event.remove(engine, "before_cursor_execute", _on_sql)
    if prev is None:
        app.dependency_overrides.pop(require_login, None)
    else:
        app.dependency_overrides[require_login] = prev


async def _get(url: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        return await ac.get(url)


async def test_selected_repo_report_runs_no_sql_on_the_event_loop_thread(world, db):
    """🔴 수정 전 실측 — 리포 조회 + 집계 6개가 루프 스레드에서 돌았다."""
    # 양성 대조 — 루프 스레드에서 돈 문장은 계기가 루프 스레드로 적는다.
    # Positive control: a statement on the loop is recorded as the loop thread.
    db.execute(text("SELECT 1"))
    assert world.sql_threads, "계기가 루프 스레드의 문장을 못 봤다"
    assert all(thread is world.loop_thread for thread in world.sql_threads), world.sql_threads
    world.sql_threads.clear()

    resp = await _get(f"/dashboard?mode=repos&days=30&repo={_REPO}")

    assert resp.status_code == 200
    # 레포트가 실제로 만들어졌다 — 안 만들어졌으면 «루프 밖» 단언이 공허하다.
    # The report was actually built; otherwise the off-loop assertion would be vacuous.
    assert _REPO in resp.text
    assert world.sql_threads, "문장이 하나도 기록되지 않았다(공허)"
    on_loop = sum(1 for thread in world.sql_threads if thread is world.loop_thread)
    assert on_loop == 0, f"루프 스레드에서 돈 문장 {on_loop}/{len(world.sql_threads)}"


def test_the_report_keeps_the_ownership_rule(world, db):
    """옮긴 도우미도 같은 소유 판정 — 내 리포 · 소유자 없는(레거시) 리포는 레포트, 남의 리포 · 없는 리포는 None."""
    mine = db.query(Repository).filter(Repository.full_name == _REPO).one()
    other = User(github_id=f"rr-{uuid.uuid4().hex[:8]}", github_login="other", email="o@x.com",
                 display_name="O")
    db.add(other)
    db.commit()
    db.add_all([Repository(full_name="someone-else/private", user_id=other.id),
                Repository(full_name="legacy/unowned", user_id=None)])
    db.commit()

    def report(name: str):
        return dashboard_route._build_repo_report(db, mine.user_id, name, 30)  # pylint: disable=protected-access

    assert report(_REPO)["repo_full_name"] == _REPO
    assert report("legacy/unowned")["repo_full_name"] == "legacy/unowned"
    assert report("someone-else/private") is None
    assert report("nobody/nothing") is None
