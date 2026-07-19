"""인앱 스케줄러 정합 (2026-07-19 P0 — Railway cron 미실행 사고 봉인).

🔴 사고: `railway.toml` 의 `[[deploy.cronJobs]]` 는 **Railway 스키마에 존재하지 않는 키**라
조용히 무시됐다. Railway cron 은 서비스당 **단일 `cronSchedule`**(대시보드 또는 config-as-code
`deploy.cronSchedule`)이며 배열을 지원하지 않는다. 실측: SCAManager 서비스 `cronSchedule=null`
· `nextCronRunAt=null` → weekly/trend/retry/orphan/retention **5종 전부 한 번도 실행 안 됨**.
결정적 증거 = 20:00 UTC 스윕 3.5시간 경과 후에도 만료 캐시 8건 잔존(`purge_expired` 는
`expires_at < now` 를 지우므로 실행됐다면 0이어야 함).
Incident: `[[deploy.cronJobs]]` is not a Railway config key — silently ignored. All 5 crons had
never run. Replaced with an in-app scheduler so wiring is asserted by tests, not invisible config.

커버리지 구성: 순수 시각 계산 + 기동 조건 + JOBS 배선 + **job 본문 호출**·**루프 실패 격리**·
start/stop 생명주기. 🔴 실제 대기 시간은 단언하지 않는다(flaky) — 대신 `every_seconds=0` 으로
루프를 즉시 돌려 동작만 검증한다.
Covers pure math, start conditions, JOBS wiring, job bodies, loop failure isolation and lifecycle.
Real sleep durations are never asserted (would flake).
"""
import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src import scheduler as sched
from src.scheduler import JOBS, next_daily_run, next_weekly_run, scheduler_enabled


def _utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


# ── next_daily_run ───────────────────────────────────────────────────────


def test_daily_run_later_today():
    """오늘 아직 안 지난 시각이면 오늘 그 시각."""
    got = next_daily_run(_utc(2026, 7, 19, 10, 0), hour=20, minute=0)
    assert got == _utc(2026, 7, 19, 20, 0)


def test_daily_run_rolls_to_tomorrow_when_passed():
    """🔴 이미 지난 시각이면 내일 — 지난 시각을 즉시 재실행하지 않는다."""
    got = next_daily_run(_utc(2026, 7, 19, 23, 36), hour=20, minute=0)
    assert got == _utc(2026, 7, 20, 20, 0)


def test_daily_run_exact_boundary_rolls_forward():
    """정확히 스케줄 시각이면 다음 날 — 같은 tick 중복 실행 차단."""
    got = next_daily_run(_utc(2026, 7, 19, 20, 0), hour=20, minute=0)
    assert got == _utc(2026, 7, 20, 20, 0)


def test_daily_run_crosses_month_boundary():
    got = next_daily_run(_utc(2026, 7, 31, 23, 0), hour=3, minute=0)
    assert got == _utc(2026, 8, 1, 3, 0)


# ── next_weekly_run ──────────────────────────────────────────────────────


def test_weekly_run_same_day_before_time():
    """월요일 이른 시각 → 그날 그 시각 (weekday 0 = 월)."""
    # 2026-07-20 은 월요일 / Monday
    got = next_weekly_run(_utc(2026, 7, 20, 0, 0) .replace(hour=0, minute=0), weekday=0, hour=9, minute=0)
    assert got == _utc(2026, 7, 20, 9, 0)


def test_weekly_run_rolls_to_next_week_when_passed():
    """🔴 해당 요일 시각이 지났으면 다음 주 — 지난 주기를 몰아 실행하지 않는다."""
    got = next_weekly_run(_utc(2026, 7, 20, 10, 0), weekday=0, hour=0, minute=0)
    assert got == _utc(2026, 7, 27, 0, 0)


def test_weekly_run_from_midweek():
    """수요일에서 다음 월요일로."""
    got = next_weekly_run(_utc(2026, 7, 22, 12, 0), weekday=0, hour=0, minute=0)
    assert got == _utc(2026, 7, 27, 0, 0)


# ── scheduler_enabled (기동 조건) ────────────────────────────────────────


class _S:
    def __init__(self, is_production=True, scheduler_disabled=False):
        self.is_production = is_production
        self.scheduler_disabled = scheduler_disabled


def test_enabled_in_production_by_default():
    assert scheduler_enabled(_S()) is True


def test_disabled_outside_production():
    """🔴 비운영(테스트/로컬)에서는 미기동 — TestClient lifespan 이 태스크를 띄우면 안 된다."""
    assert scheduler_enabled(_S(is_production=False)) is False


def test_kill_switch_overrides_production():
    """🔴 운영 사고 시 즉시 비활성 (기존 *_DISABLED 패턴 페어)."""
    assert scheduler_enabled(_S(scheduler_disabled=True)) is False


# ── JOBS 레지스트리 (배선 단언 — 이번 사고의 핵심) ───────────────────────


def test_all_cron_jobs_registered():
    """🔴 cron job 전수 등록 — 배선을 테스트로 단언.

    이번 사고의 근본은 '설정이 저장소 밖에 있어 어긋나도 아무도 모른다' 였다.
    🔴 `scan-security` 는 2026-07-19 사용자 결정으로 편입 — 그전엔 **엔드포인트만 있고
    스케줄러 job 이 없어 출시 이래 실행 0회**였고, 파리티 가드가 그 갭을 표면화했다.
    """
    names = {j.name for j in JOBS}
    assert names == {
        "retry-pending-merges", "sweep-orphans", "trend", "retention-sweep", "weekly-reports",
        "scan-security",
    }, f"등록 누락/오타: {names}"


def test_job_schedules_match_previous_cron_expressions():
    """🔴 구 railway.toml 스케줄과 동일 — 주기가 조용히 바뀌면 운영 동작이 달라진다."""
    by_name = {j.name: j for j in JOBS}
    assert by_name["retry-pending-merges"].every_seconds == 60          # * * * * *
    assert by_name["sweep-orphans"].every_seconds == 600                # */10 * * * *
    assert by_name["trend"].daily_at == (3, 0)                          # 0 3 * * *
    assert by_name["retention-sweep"].daily_at == (20, 0)               # 0 20 * * *
    assert by_name["weekly-reports"].weekly_at == (0, 0, 0)             # 0 0 * * 1 (월 00:00)


def test_scan_security_schedule_is_daily_at_0400():
    """🔴 scan-security 는 구 railway.toml 에 **없던** 신규 주기 — 위 테스트와 분리한 이유다.

    나머지 5종은 '구 cron 표현식과 동일'이 단언 근거지만, 이 job 은 2026-07-19 사용자 결정으로
    처음 스케줄된다(그전엔 엔드포인트만 존재). 주기 변경은 GitHub API 쿼터 소모 패턴을 바꾼다.
    Separate from the parity test above: this job has no prior cron expression to match.
    """
    by_name = {j.name: j for j in JOBS}
    assert by_name["scan-security"].daily_at == (4, 0)                  # 0 4 * * *


def test_every_job_has_exactly_one_schedule_kind():
    """각 job 은 interval/daily/weekly 중 정확히 하나 — 중복 지정 시 동작 모호."""
    for job in JOBS:
        kinds = [job.every_seconds is not None, job.daily_at is not None, job.weekly_at is not None]
        assert sum(kinds) == 1, f"{job.name}: 스케줄 종류 {sum(kinds)}개"


def test_every_job_is_callable():
    """🔴 job 이 실제 호출 가능한 함수를 물고 있어야 한다 — 이름만 있으면 dead 배선."""
    for job in JOBS:
        assert callable(job.run), f"{job.name}: run 이 호출 불가"


# ── job 본문 / 루프 / 기동·정지 (동작 커버리지) ──────────────────────────


class _FakeSession:
    """SessionLocal() 컨텍스트 매니저 대역."""

    def __enter__(self):
        return MagicMock()

    def __exit__(self, *exc):
        return False


def _patch_session(monkeypatch):
    # `lambda: _FakeSession()` 는 `_FakeSession` 과 동일 (py/unnecessary-lambda).
    monkeypatch.setattr("src.scheduler.SessionLocal", _FakeSession)


# ── _seconds_until_next (스케줄 종류별 분기) ─────────────────────────────


def test_seconds_until_next_interval_job():
    job = sched.Job("t", lambda: None, every_seconds=60)
    assert sched._seconds_until_next(job, _utc(2026, 7, 19, 10, 0)) == 60


def test_seconds_until_next_daily_job():
    job = sched.Job("t", lambda: None, daily_at=(20, 0))
    got = sched._seconds_until_next(job, _utc(2026, 7, 19, 19, 30))
    assert got == 30 * 60


def test_seconds_until_next_weekly_job():
    """월요일 00:00 기준 — 같은 시각이면 다음 주(7일)."""
    job = sched.Job("t", lambda: None, weekly_at=(0, 0, 0))
    got = sched._seconds_until_next(job, _utc(2026, 7, 20, 0, 0))
    assert got == 7 * 24 * 3600


# ── job 본문 — 서비스 함수를 실제로 호출하는가 ───────────────────────────


async def test_retry_job_calls_service(monkeypatch):
    """🔴 job 이 서비스 함수를 실제 호출 — 배선이 없으면 스케줄러는 껍데기다."""
    _patch_session(monkeypatch)
    called = {}

    async def fake(db, limit):
        called["limit"] = limit
        return {"ok": 1}

    monkeypatch.setattr("src.scheduler.process_pending_retries", fake)
    await sched._retry_pending_merges()
    assert "limit" in called, "process_pending_retries 미호출"


async def test_sweep_orphans_job_calls_service(monkeypatch):
    _patch_session(monkeypatch)
    called = {}

    async def fake(db):
        called["hit"] = True
        return 0

    monkeypatch.setattr("src.scheduler.sweep_analysis_attempts", fake)
    await sched._sweep_orphans()
    assert called.get("hit")


async def test_retention_job_calls_service(monkeypatch):
    _patch_session(monkeypatch)
    called = {}
    monkeypatch.setattr(
        "src.scheduler.run_retention_sweep",
        lambda db: called.setdefault("hit", True) or {"expired_cache": 0},
    )
    await sched._retention_sweep()
    assert called.get("hit")


async def test_trend_job_calls_service(monkeypatch):
    _patch_session(monkeypatch)
    called = {}

    async def fake(db):
        called["hit"] = True
        return 0

    monkeypatch.setattr("src.scheduler.run_trend_check", fake)
    await sched._trend_check()
    assert called.get("hit")


async def test_weekly_job_calls_service(monkeypatch):
    _patch_session(monkeypatch)
    called = {}

    async def fake(db):
        called["hit"] = True
        return 0

    monkeypatch.setattr("src.scheduler.run_weekly_reports", fake)
    await sched._weekly_reports()
    assert called.get("hit")


async def test_scan_security_job_calls_service(monkeypatch):
    """🔴 신규 편입 job 도 본문 배선 단언 — 등록만 되고 본문이 비면 결과는 '실행 0회'와 같다.

    이 PR 이 해소하는 갭(엔드포인트만 있고 스케줄 job 없음)의 거울상: job 은 있는데 서비스를
    안 부르는 껍데기. 나머지 5종과 동일한 패턴으로 봉인한다.
    """
    _patch_session(monkeypatch)
    called = {}

    async def fake(db):
        called["hit"] = True
        return {"code_scanning": 0, "secret_scanning": 0, "skipped": 0, "repos": 0}

    monkeypatch.setattr("src.scheduler.scan_all_repos", fake)
    await sched._scan_security()
    assert called.get("hit")


# ── 루프 격리 — 실패가 스케줄러를 멈추면 안 된다 ─────────────────────────


async def test_job_failure_does_not_kill_loop():
    """🔴 job 이 예외를 던져도 루프는 계속 — 한 번 실패로 주기 작업이 영구 정지하면 안 된다.

    이번 사고의 형태(조용히 안 도는 cron)와 같은 결과를 코드 안에서 재현하지 않기 위함.
    """
    calls = []

    async def boom():
        calls.append(1)
        raise RuntimeError("의도적 실패")

    task = asyncio.create_task(sched._run_job_forever(sched.Job("t", boom, every_seconds=0)))
    await asyncio.sleep(0.05)
    task.cancel()
    # 🔴 `await task` 대신 wait_for — 취소가 전파되지 않으면 무한 대기가 되므로 상한을 둔다
    # (부수 효과: py/ineffectual-statement 오탐도 해소).
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)
    assert len(calls) >= 2, f"실패 후 재실행 안 됨 (호출 {len(calls)}회)"


async def test_cancellation_propagates():
    """취소는 삼키지 않는다 — 종료 시 태스크가 남으면 안 된다."""
    async def never():
        await asyncio.sleep(3600)

    task = asyncio.create_task(sched._run_job_forever(sched.Job("t", never, every_seconds=0)))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1)


# ── start / stop ─────────────────────────────────────────────────────────


def test_start_returns_no_tasks_when_disabled():
    assert sched.start(_S(is_production=False)) == []


async def test_start_creates_one_task_per_job_and_stop_cancels():
    """🔴 기동 시 JOBS 수만큼 태스크 생성, 정지 시 전부 종료 — 누수 차단."""
    tasks = sched.start(_S())
    try:
        assert len(tasks) == len(sched.JOBS)
    finally:
        await sched.stop(tasks)
    assert all(t.done() for t in tasks), "stop 후 살아있는 태스크 존재"


async def test_stop_is_safe_on_empty_list():
    """미기동(빈 목록) 정지도 안전 — lifespan finally 에서 항상 호출된다."""
    await sched.stop([])
