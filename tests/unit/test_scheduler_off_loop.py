"""스케줄러 job 은 동기 DB 문장을 이벤트 루프 스레드에서 실행하지 않는다.

Scheduler jobs never execute a synchronous DB statement on the event-loop thread.

운영(앱 us-east4 ↔ DB ap-southeast-2, 왕복 ≈ 0.2 s)에서 1분마다 도는 retry-pending-merges 가
**빈 큐**에서도 루프를 ≈ 0.78 s 세웠다 — 루프 지연 프로브 경고 193건 중 161건이 그 job 과 한 박자였다.
claim(`FOR UPDATE SKIP LOCKED`)·세션 반납(ROLLBACK)이 루프 위에서 동기로 돌았다. 그동안 같은
프로세스의 모든 요청(웹훅 202 포함)이 선다.
In production the every-minute retry job blocked the loop ~0.78 s even on an empty queue.

계기 — job 본문(`JOBS[*].run`)을 **이 테스트의 루프에서** 그대로 돌린다. 그래서 루프 스레드 =
테스트 코루틴의 스레드다. 엔진의 `before_cursor_execute` 가 문장마다, `commit`·`rollback` 이
트랜잭션 끝마다, 풀의 `checkout`·`reset` 이 연결 대여·반납(운영에서는 pre-ping·ROLLBACK 왕복)마다
실행 스레드를 적는다 — 운영 PG 에서는 전부 왕복이다. GitHub·Telegram 가짜는 루프에서 await 되며
루프 스레드를 적는다 — 계기가 두 스레드를 구별한다는 양성 대조다.
Instrument: each job body runs on this test's loop. The engine records the thread of every
statement, COMMIT/ROLLBACK and pool checkout/reset (each a round trip on production PG); the HTTP
fakes, awaited on the loop, record the loop thread as the positive control.
"""
# pylint: disable=redefined-outer-name
from __future__ import annotations

import asyncio
import contextlib
import threading
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.concurrency import run_in_threadpool

from src import scheduler
from src.database import Base
from src.models.analysis import Analysis
from src.models.analysis_attempt import AnalysisAttempt
from src.models.insight_narrative_cache import InsightNarrativeCache
from src.models.merge_retry import MergeRetryQueue
from src.models.repo_config import RepoConfig
from src.models.repository import Repository
from src.models.security_alert_log import SecurityAlertProcessLog
from src.models.user import User
from src.repositories import insight_narrative_cache_repo, merge_retry_repo
from src.services import cron_service, merge_retry_service, security_scan_service

# job 이 읽고 쓰는 테이블이 등록돼야 한다 — 튜플을 **읽어** import 소실을 loud-fail 한다.
# Tables the jobs touch must be registered; reading the tuple loud-fails a lost import.
_TABLE_MODELS = (Analysis, AnalysisAttempt, InsightNarrativeCache, MergeRetryQueue, RepoConfig,
                 Repository, SecurityAlertProcessLog, User)
if any(m.__tablename__ not in Base.metadata.tables for m in _TABLE_MODELS):
    raise RuntimeError("ORM import 소실 — 테이블 미등록 / ORM import lost, table unregistered")

_JOBS = {j.name: j for j in scheduler.JOBS}
_REPO = "offloop/sched"
_NOW = datetime.now(timezone.utc).replace(tzinfo=None)


# ─── 계기 ──────────────────────────────────────────────────────────────────────


class _RecordingSession(Session):
    """close 시각·스레드를 적는 세션 — 세션 반납이 스레드 작업과 겹치는지 본다.
    A session that records when and where it is closed."""

    closes: list = []

    def close(self) -> None:
        type(self).closes.append((time.perf_counter(), threading.current_thread()))
        super().close()


@pytest.fixture()
def world(monkeypatch):
    """스레드 사이에서 넘겨 쓸 수 있는 인메모리 SQLite + 스레드 기록기 + 스케줄러 세션 교체.

    In-memory SQLite shareable across threads (one thread at a time, like the production pool),
    the thread recorders, and the scheduler's session factory swapped for it.
    `expire_on_commit` 은 운영(`src/database.py`)처럼 기본값 — 커밋 뒤 ORM 속성 읽기가 SELECT 가 되는
    축을 지우지 않는다.
    """
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    _RecordingSession.closes = []
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False,
                           class_=_RecordingSession)
    w = SimpleNamespace(factory=factory, loop_thread=threading.current_thread(),
                        sql=[], conn=[], http=[])

    def _on_sql(_conn, _cursor, statement, *_a, **_k):
        w.sql.append((threading.current_thread(), statement))

    def _on_conn(name):
        def _record(*_a, **_k):
            w.conn.append((threading.current_thread(), name))
        return _record

    event.listen(engine, "before_cursor_execute", _on_sql)
    # 풀(checkout·reset)과 연결(commit·rollback) 이벤트 — 둘 다 엔진에 건다.
    # Pool (checkout/reset) and connection (commit/rollback) events, both on the engine.
    for name in ("checkout", "reset", "commit", "rollback"):
        event.listen(engine, name, _on_conn(name))
    monkeypatch.setattr(scheduler, "SessionLocal", factory)
    monkeypatch.delenv("SECURITY_AUTO_PROCESS_DISABLED", raising=False)

    def reset_records():
        w.sql.clear()
        w.conn.clear()
        w.http.clear()
        _RecordingSession.closes = []

    w.reset_records = reset_records
    yield w
    engine.dispose()


def _http(w, name, result=None, exc=None):
    """루프에서 await 되는 HTTP 가짜 — 부른 스레드를 적는다(양성 대조).
    An HTTP fake awaited on the loop; records its thread (positive control)."""
    async def fake(*args, **_kwargs):
        w.http.append((threading.current_thread(), name))
        value = result(*args) if callable(result) else result
        if exc is not None:
            raise exc
        return value
    return fake


def _assert_off_loop(w, *, expect_http: bool, expect: frozenset = frozenset({"checkout", "reset"})) -> None:
    """기록 전체를 판정한다 — `expect` 는 반드시 잡혔어야 하는 연결 이벤트(없으면 단언이 공허하다)."""
    assert w.sql, "SQL 이 한 문장도 안 잡혔다 — 엔진 기록기가 공허하다"
    on_loop = [stmt.split()[0] for t, stmt in w.sql if t is w.loop_thread]
    assert not on_loop, (
        f"이벤트 루프 스레드에서 실행된 SQL {len(on_loop)}/{len(w.sql)}: {on_loop[:8]}")
    missing = expect - {name for _, name in w.conn}
    assert not missing, f"기대한 연결 이벤트가 안 잡혔다 — 시나리오가 그 경로를 안 탔다: {sorted(missing)}"
    conn_on_loop = [name for t, name in w.conn if t is w.loop_thread]
    assert not conn_on_loop, (
        f"연결 대여·반납·COMMIT·ROLLBACK 이 루프 스레드에서(운영에서는 왕복): {conn_on_loop}")
    assert _RecordingSession.closes, "세션이 닫히지 않았다"
    closes_on_loop = [t for _, t in _RecordingSession.closes if t is w.loop_thread]
    assert not closes_on_loop, "세션 close 가 루프 스레드에서 돌았다"
    if expect_http:
        assert w.http, "HTTP 가짜가 한 번도 안 불렸다 — 시나리오가 공허하다"
        off = [name for t, name in w.http if t is not w.loop_thread]
        assert not off, f"비동기 HTTP 가 루프 밖에서 불렸다: {off}"


_WRITES = frozenset({"checkout", "reset", "commit"})
_ROLLS_BACK = frozenset({"checkout", "reset", "rollback"})


# ─── 시나리오 — job 마다 DB 경로를 실제로 태운다 ─────────────────────────────────


def _seed_retry_rows(db) -> dict[int, int]:
    """분기마다 PR 하나 — {pr_number: queue row id}."""
    repo = Repository(full_name=_REPO)
    db.add(repo)
    db.add(RepoConfig(repo_full_name=_REPO, auto_merge=True, merge_threshold=75,
                      notify_chat_id="-100cfg", auto_merge_issue_on_failure=True))
    db.commit()
    specs = {
        1: {"attempts_count": 30},   # 시도 한도 소진 → abandoned
        2: {"score": 50},            # 설정 변경(점수 < 임계) → abandoned + 알림
        3: {},                       # PR 조회 실패 → released
        4: {},                       # 이미 머지됨 → succeeded
        5: {},                       # SHA drift → abandoned
        6: {},                       # 머지 성공 → succeeded + 알림
        7: {},                       # 종결 실패 → failed_terminal + 알림 + 이슈
        8: {},                       # 일시 실패 → released
        9: {},                       # 인프라 오류 → 복구·해제(released)
    }
    ids = {}
    for pr, over in specs.items():
        analysis = Analysis(repo_id=repo.id, commit_sha=f"sha{pr}", score=90, grade="A", result={})
        db.add(analysis)
        db.flush()
        row = MergeRetryQueue(
            repo_full_name=_REPO, pr_number=pr, analysis_id=analysis.id, commit_sha=f"sha{pr}",
            score=over.get("score", 90), threshold_at_enqueue=75, status="pending",
            attempts_count=over.get("attempts_count", 1), max_attempts=30,
            next_retry_at=_NOW - timedelta(seconds=10), notify_chat_id="-100row",
        )
        db.add(row)
        db.flush()
        ids[pr] = row.id
    db.commit()
    return ids


def _patch_retry_http(w, monkeypatch) -> None:
    def pr_data(_token, _repo, pr):
        if pr == 3:
            return None
        head = "drifted" if pr == 5 else f"sha{pr}"
        return {"merged": pr == 4, "head": {"sha": head}, "base": {"ref": "main"}}

    def merge_result(_token, _repo, pr):
        if pr == 9:
            raise httpx.ConnectError("net down")
        if pr == 6:
            return True, None, None
        if pr == 7:
            return False, "permission_denied: 403", None
        return False, "unstable_ci: state=unstable", None

    async def merge_pr(token, repo, pr, **_kwargs):
        w.http.append((threading.current_thread(), "merge_pr"))
        return merge_result(token, repo, pr)

    monkeypatch.setattr(merge_retry_service, "_get_pr_data", _http(w, "pr_data", pr_data))
    monkeypatch.setattr(merge_retry_service, "merge_pr", merge_pr)
    monkeypatch.setattr(merge_retry_service, "_get_ci_status_safe",
                        _http(w, "ci_status", lambda *_a: "running"))
    monkeypatch.setattr(merge_retry_service, "telegram_post_message", _http(w, "telegram"))
    monkeypatch.setattr(merge_retry_service, "create_merge_failure_issue", _http(w, "issue"))
    monkeypatch.setattr(merge_retry_service.settings, "telegram_bot_token", "123:ABC")


def _statuses(w) -> dict[int, str]:
    with w.factory() as db:
        return {r.pr_number: r.status for r in db.query(MergeRetryQueue).all()}


async def _run(name):
    await _JOBS[name].run()


async def test_retry_job_every_branch_runs_its_db_work_off_the_loop(world, monkeypatch):
    """🔴 수정 전 실측 — claim·쓰기·세션 반납이 전부 루프 스레드였다.

    9개 분기(한도 소진·설정 변경·조회 실패·이미 머지·SHA drift·성공·종결·일시·인프라 오류)를
    한 배치로 태운다. 행마다 write-back 이 커밋해 세션 전체가 만료되므로, 루프가 ORM 속성을
    읽기만 해도 SELECT 가 루프에서 돈다 — 그것까지 잡는다.
    """
    with world.factory() as db:
        _seed_retry_rows(db)
    _patch_retry_http(world, monkeypatch)
    world.reset_records()

    await _run("retry-pending-merges")

    # 확인 조회는 루프에서 돈다 — 기록을 먼저 판정한다. / Judge the records before verifying on the loop.
    _assert_off_loop(world, expect_http=True, expect=_WRITES | {"rollback"})
    assert _statuses(world) == {
        1: "abandoned", 2: "abandoned", 3: "pending", 4: "succeeded", 5: "abandoned",
        6: "succeeded", 7: "failed_terminal", 8: "pending", 9: "pending",
    }
    called = {name for _, name in world.http}
    assert {"pr_data", "merge_pr", "ci_status", "telegram", "issue"} <= called, called


async def test_retry_job_without_a_token_releases_off_the_loop(world, monkeypatch):
    """토큰이 없는 행 — 소유자·전역 토큰 조회와 해제가 루프 밖에서."""
    with world.factory() as db:
        _seed_retry_rows(db)
    monkeypatch.setattr(merge_retry_service.settings, "github_token", "")
    world.reset_records()

    await _run("retry-pending-merges")

    _assert_off_loop(world, expect_http=False, expect=_WRITES)
    statuses = _statuses(world)
    assert statuses[3] == "pending" and statuses[1] == "abandoned", statuses


async def test_empty_queue_is_one_statement_off_the_loop(world):
    """🔴 운영에서 경고를 낸 모양 그대로 — 빈 큐. 문장은 claim SELECT 하나(늘지 않는다)이고 루프 밖이다.
    The measured shape: an empty queue is one claim SELECT, and it runs off the loop."""
    world.reset_records()

    await _run("retry-pending-merges")

    statements = [stmt for _, stmt in world.sql]
    assert len(statements) == 1, statements
    assert "merge_retry_queue" in statements[0] and statements[0].lstrip().startswith("SELECT")
    _assert_off_loop(world, expect_http=False)


async def test_sweep_orphans_job_runs_its_db_work_off_the_loop(world, monkeypatch):
    with world.factory() as db:
        repo = Repository(full_name=_REPO)
        db.add(repo)
        db.commit()
        for i in range(2):
            db.add(AnalysisAttempt(repo_id=repo.id, commit_sha=f"gone{i}", event="push",
                                   started_at=_NOW - timedelta(minutes=60 + i)))
        db.add(AnalysisAttempt(repo_id=repo.id, commit_sha="inflight", event="push",
                               started_at=_NOW - timedelta(minutes=1)))
        db.commit()
    monkeypatch.setattr(cron_service.settings, "telegram_bot_token", "123:ABC")
    monkeypatch.setattr(cron_service.settings, "telegram_chat_id", "-100ops")
    monkeypatch.setattr(cron_service, "telegram_post_message", _http(world, "telegram"))
    world.reset_records()

    await _run("sweep-orphans")

    _assert_off_loop(world, expect_http=True, expect=_WRITES)
    with world.factory() as db:
        assert [a.commit_sha for a in db.query(AnalysisAttempt).all()] == ["inflight"]


def _seed_repo_with_history(db) -> None:
    """채팅 id 가 있는 리포 + 지난주 90점 5건 · 이번 주 60점 5건(추세 하락 30점)."""
    repo = Repository(full_name=_REPO, telegram_chat_id="-100repo")
    db.add(repo)
    db.commit()
    for i in range(5):
        db.add(Analysis(repo_id=repo.id, commit_sha=f"now{i}", score=60, grade="C", result={},
                        created_at=_NOW - timedelta(days=1, hours=i)))
        db.add(Analysis(repo_id=repo.id, commit_sha=f"prev{i}", score=90, grade="A", result={},
                        created_at=_NOW - timedelta(days=9, hours=i)))
    db.commit()


@pytest.mark.parametrize("name", ["trend", "weekly-reports"])
async def test_report_jobs_run_their_db_work_off_the_loop(world, monkeypatch, name):
    with world.factory() as db:
        _seed_repo_with_history(db)
    monkeypatch.setattr(cron_service.settings, "telegram_chat_id", "")
    sent = []

    async def telegram(_token, chat_id, payload):
        world.http.append((threading.current_thread(), "telegram"))
        sent.append((chat_id, payload["text"]))

    monkeypatch.setattr(cron_service, "telegram_post_message", telegram)
    world.reset_records()

    await _run(name)

    assert [chat for chat, _ in sent] == ["-100repo"], sent
    _assert_off_loop(world, expect_http=True)


async def test_retention_job_runs_its_db_work_off_the_loop(world):
    with world.factory() as db:
        insight_narrative_cache_repo.upsert(
            db, user_id=1, days=7, response={"s": 1}, ttl_seconds=1,
            now=datetime.now(timezone.utc) - timedelta(hours=1))
        repo = Repository(full_name=_REPO)
        db.add(repo)
        db.commit()
        analysis = Analysis(repo_id=repo.id, commit_sha="old", score=80, grade="B", result={})
        db.add(analysis)
        db.commit()
        row = MergeRetryQueue(
            repo_full_name=_REPO, pr_number=1, analysis_id=analysis.id, commit_sha="old",
            score=80, threshold_at_enqueue=75, status="succeeded", next_retry_at=_NOW)
        db.add(row)
        db.commit()
        row.updated_at = _NOW - timedelta(days=10)
        db.commit()
    world.reset_records()

    await _run("retention-sweep")

    _assert_off_loop(world, expect_http=False, expect=_WRITES)
    with world.factory() as db:
        assert db.query(InsightNarrativeCache).count() == 0
        assert db.query(MergeRetryQueue).count() == 0


async def test_scan_security_job_runs_its_db_work_off_the_loop(world, monkeypatch):
    with world.factory() as db:
        owner = User(github_id=77, github_login="own", email="o@x.com", display_name="O")
        db.add(owner)
        db.commit()
        db.add(Repository(full_name=_REPO, user_id=owner.id))
        db.add(Repository(full_name="offloop/legacy"))
        db.commit()

    def alerts(_token, _repo, kind):
        if kind == "code-scanning":
            return [{"number": 1, "rule": {"id": "py/a", "severity": "error"}},
                    {"number": 2, "rule": {"id": "py/b", "severity": "warning"}}]
        return [{"number": 3, "secret_type": "github_pat"}]

    monkeypatch.setattr(security_scan_service, "_fetch_alerts", _http(world, "alerts", alerts))
    world.reset_records()

    await _run("scan-security")

    _assert_off_loop(world, expect_http=True, expect=_WRITES)
    with world.factory() as db:
        assert db.query(SecurityAlertProcessLog).count() == 6


# ─── 실패 경로 — 리포별 격리의 롤백도 루프 밖에서 ─────────────────────────────────


@pytest.mark.parametrize("name", ["trend", "weekly-reports"])
async def test_report_job_failure_rolls_back_off_the_loop(world, monkeypatch, name):
    """Telegram 실패 → 리포별 격리가 세션을 롤백한다. 그 ROLLBACK 도 운영에서는 왕복이다."""
    with world.factory() as db:
        _seed_repo_with_history(db)
    monkeypatch.setattr(cron_service.settings, "telegram_chat_id", "")
    monkeypatch.setattr(cron_service, "telegram_post_message",
                        _http(world, "telegram", exc=httpx.ConnectError("down")))
    world.reset_records()

    await _run(name)

    _assert_off_loop(world, expect_http=True, expect=_ROLLS_BACK)


@pytest.mark.parametrize("failure", ["fetch", "upsert"])
async def test_scan_security_failure_rolls_back_off_the_loop(world, monkeypatch, failure):
    """fetch 가 새면 리포 단위, upsert 가 실패하면 alert 단위로 롤백한다 — 둘 다 루프 밖에서."""
    with world.factory() as db:
        db.add(Repository(full_name=_REPO))
        db.commit()
    alerts = [{"number": 1, "rule": {"id": "py/a", "severity": "error"}}]
    if failure == "fetch":
        fetch = _http(world, "alerts", exc=httpx.ConnectError("down"))
    else:
        fetch = _http(world, "alerts", lambda *_a: alerts)
        real = security_scan_service.security_alert_log_repo.upsert_alert_log

        def flaky_upsert(db, **kwargs):
            db.execute(text("SELECT 1"))  # 트랜잭션을 열어 둔다 — 롤백할 것이 있게
            if kwargs["alert_type"] == "code_scanning":
                raise SQLAlchemyError("boom")
            return real(db, **kwargs)

        monkeypatch.setattr(security_scan_service.security_alert_log_repo, "upsert_alert_log",
                            flaky_upsert)
    monkeypatch.setattr(security_scan_service, "_fetch_alerts", fetch)
    world.reset_records()

    await _run("scan-security")

    _assert_off_loop(world, expect_http=True, expect=_ROLLS_BACK)


# 🔴 새 job 은 여기에 시나리오를 더해야 한다 — 없으면 아래 테스트가 red 다(«루프 밖» 은 job 마다 증명한다).
# A new job must add a scenario here; otherwise the test below goes red.
_COVERED = {
    "retry-pending-merges": test_retry_job_every_branch_runs_its_db_work_off_the_loop,
    "sweep-orphans": test_sweep_orphans_job_runs_its_db_work_off_the_loop,
    "trend": test_report_jobs_run_their_db_work_off_the_loop,
    "weekly-reports": test_report_jobs_run_their_db_work_off_the_loop,
    "retention-sweep": test_retention_job_runs_its_db_work_off_the_loop,
    "scan-security": test_scan_security_job_runs_its_db_work_off_the_loop,
}


def test_every_scheduled_job_has_an_off_loop_scenario():
    assert set(_COVERED) == set(_JOBS), (
        f"시나리오 없는 job: {sorted(set(_JOBS) - set(_COVERED))} · "
        f"사라진 job: {sorted(set(_COVERED) - set(_JOBS))}")


# ─── 계기 자체 — 루프 SQL 은 잡고, 워커 SQL 은 기록하되 세지 않는다 ────────────────


async def test_recorder_tells_loop_sql_from_worker_sql(world):
    """계기 뒤집기 — 루프에서 실행한 문장은 루프로, 워커 스레드의 문장은 워커로 적힌다.
    Instrument flip: a statement on the loop is attributed to the loop, a worker one to the worker."""
    world.reset_records()
    db = world.factory()
    db.execute(text("SELECT 1"))                               # 루프 — 잡혀야 한다
    await run_in_threadpool(db.execute, text("SELECT 2"))      # 워커 — 적히되 루프가 아니다
    await run_in_threadpool(db.close)

    assert [stmt for _, stmt in world.sql] == ["SELECT 1", "SELECT 2"]
    assert world.sql[0][0] is world.loop_thread
    assert world.sql[1][0] is not world.loop_thread
    with pytest.raises(AssertionError, match="이벤트 루프 스레드에서 실행된 SQL 1/2"):
        _assert_off_loop(world, expect_http=False)


# ─── 느린 claim 이 같은 루프의 다른 코루틴을 세우지 않는다 ──────────────────────────


async def test_slow_claim_does_not_stall_a_concurrent_ticker(world, monkeypatch):
    """🔴 claim 이 0.5 s 동안 동기로 막혀도 같은 루프의 10 ms 티커는 계속 돈다.

    수정 전에는 티커의 최대 간격이 막힌 시간 그대로(≥ 0.5 s)였다 — 운영 경고와 같은 모양.
    Before the fix the ticker's largest gap equalled the stall, the shape of the production warning.
    """
    slow = 0.5
    real = merge_retry_repo.claim_batch
    slow_calls = []

    def slow_claim(*a, **k):
        slow_calls.append(threading.current_thread())
        time.sleep(slow)
        return real(*a, **k)

    monkeypatch.setattr(merge_retry_repo, "claim_batch", slow_claim)
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
    await _run("retry-pending-merges")
    elapsed = time.perf_counter() - started
    done.set()
    await tick

    # 양성 대조 — 느린 claim 이 실제로 불렸고 job 은 실제로 그만큼 걸렸다.
    # Positive control: the slow claim ran and the job really took that long.
    assert slow_calls, "느린 claim 이 불리지 않았다 — 측정이 공허하다"
    assert elapsed >= slow
    assert max(gaps) < 0.25, f"티커 최대 간격 {max(gaps):.3f}s — claim 이 루프를 {slow}s 막았다"


# ─── 종료(취소)가 와도 세션은 한 번에 한 스레드만 쓴다 ─────────────────────────────


async def test_cancel_mid_claim_closes_the_session_only_after_the_claim_thread_ends(
        world, monkeypatch):
    """🔴 스케줄러 `stop()` 은 태스크를 `Task.cancel()` 한다. `run_in_threadpool` 만으로는 그 취소가
    스레드를 두고 곧바로 올라와(실측), 호출자의 세션 close 가 **아직 claim 중인 세션**을 다른 스레드에서
    만진다. close 는 claim 스레드가 끝난 뒤, 루프 밖에서 와야 한다.

    `stop()` cancels with Task.cancel(); run_in_threadpool alone returns immediately then, and the
    caller's close would touch a session another thread is still using.
    """
    real = merge_retry_repo.claim_batch
    claim = {}

    def slow_claim(*a, **k):
        claim["start"] = time.perf_counter()
        time.sleep(0.3)
        try:
            return real(*a, **k)
        finally:
            claim["end"] = time.perf_counter()

    monkeypatch.setattr(merge_retry_repo, "claim_batch", slow_claim)
    world.reset_records()

    task = asyncio.create_task(_run("retry-pending-merges"))
    await asyncio.sleep(0.05)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # 양성 대조 — 취소가 claim 도중에 실제로 도착했다(끝난 태스크를 취소한 게 아니다).
    # Positive control: the cancellation really landed mid-claim.
    assert task.cancelled(), "취소가 claim 도중에 도착하지 않았다 — 측정이 공허하다"
    assert "end" in claim, "claim 스레드가 끝나지 않았다"
    assert _RecordingSession.closes, "세션이 닫히지 않았다 — 연결이 샌다"
    closed_at, closed_on = _RecordingSession.closes[0]
    assert closed_at >= claim["end"], (
        f"claim 스레드가 끝나기 {claim['end'] - closed_at:.3f}s 전에 세션을 닫았다 — 두 스레드가 한 세션을 썼다")
    assert closed_on is not world.loop_thread, "세션 close 가 루프 스레드에서 돌았다"
