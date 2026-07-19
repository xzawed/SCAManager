"""인앱 주기 작업 스케줄러 — Railway cron 미실행 사고(2026-07-19 P0)의 대체 기전.
In-app periodic job scheduler — replaces the Railway cron config that never ran.

🔴 사고 / Incident: `railway.toml` 의 `[[deploy.cronJobs]]` 는 **Railway 스키마에 없는 키**라
조용히 무시됐다. Railway cron 은 서비스당 **단일 `cronSchedule`** 이며 배열을 지원하지 않는다.
실측: SCAManager `cronSchedule=null`·`nextCronRunAt=null` → weekly/trend/retry/orphan/retention
5종이 **한 번도 실행되지 않았다**. 결정적 증거 = 20:00 UTC 스윕 3.5시간 경과 후에도 만료 캐시
8건 잔존(`purge_expired` 는 `expires_at < now` 를 지우므로 실행됐다면 0이어야 함).
`[[deploy.cronJobs]]` is not a Railway key — silently ignored; all 5 crons had never run.

🔴 왜 인앱인가 / Why in-app: 대시보드·외부 cron 은 **저장소 밖 설정**이라 이번처럼 어긋나도
테스트가 못 잡는다. 인앱 스케줄러는 배선을 `tests/unit/test_scheduler.py` 가 단언한다
(job 5종 등록·주기 값·호출 가능성). 의존성 추가 없이 stdlib 만 사용(정책 16).

🔴 한계 (의도적 수용) / Known limits:
- **재시작 시 daily/weekly 는 다음 주기로 밀린다.** 03:00 직후 재배포되면 그날 trend 는 건너뛴다
  (interval job 인 retry 1분·orphan 10분은 영향 없음). 상태 테이블 없이 얻는 단순성의 대가.
- **다중 인스턴스 시 중복 실행 가능.** 현재 단일 인스턴스 운영. retry 큐는 `FOR UPDATE SKIP
  LOCKED`, sweep/retention 은 멱등이라 안전하나 **weekly 리포트는 중복 발송 가능** — 수평 확장
  시 DB 잠금(advisory lock) 도입 의무.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from src.config import Settings

# 🔴 background/시스템 컨텍스트 — worker 세션(BYPASSRLS) alias 의무 (RLS Phase 2 옵션 A, db.md).
# 스케줄러 job 은 사용자 세션이 없으므로 bare SessionLocal 을 쓰면 `app.user_id` 미설정 상태로
# RLS 가 평가돼 **행이 0건으로 보이고 job 이 조용히 무동작**한다(HTTP 트리거인 `api/internal_cron`
# 이 이미 같은 이유로 background 분류). `tests/unit/test_worker_session_routing.py` 가 강제.
# Background/system context — must use the worker (BYPASSRLS) session alias; a bare SessionLocal
# would evaluate RLS with no app.user_id and silently return zero rows.
from src.database import WorkerSessionLocal as SessionLocal
from src.services.cron_service import (
    run_retention_sweep,
    run_trend_check,
    run_weekly_reports,
    sweep_analysis_attempts,
)
from src.services.merge_retry_service import process_pending_retries
from src.services.security_scan_service import scan_all_repos

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    """주기 작업 1건 — interval/daily/weekly 중 정확히 하나의 스케줄을 갖는다.
    One periodic job with exactly one schedule kind."""

    name: str
    run: Callable[[], Awaitable[None]]
    every_seconds: int | None = None
    daily_at: tuple[int, int] | None = None            # (hour, minute) UTC
    weekly_at: tuple[int, int, int] | None = None      # (weekday, hour, minute) UTC, 월=0


# ── 순수 시각 계산 ────────────────────────────────────────────────────────
# Pure scheduling math


def next_daily_run(now, hour, minute):
    """`now` 이후 첫 번째 매일 hour:minute (UTC). 정확히 같은 시각이면 다음 날.
    Next daily occurrence strictly after `now` (equal time rolls to tomorrow)."""
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(days=1)


def next_weekly_run(now, weekday, hour, minute):
    """`now` 이후 첫 번째 주간 (weekday, hour:minute) (UTC, 월=0). 같은 시각이면 다음 주.
    Next weekly occurrence strictly after `now` (Monday=0; equal time rolls a week)."""
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    candidate += timedelta(days=(weekday - now.weekday()) % 7)
    return candidate if candidate > now else candidate + timedelta(days=7)


def scheduler_enabled(settings):
    """운영 환경이고 kill-switch 가 꺼져 있을 때만 기동.
    Start only in production with the kill-switch off.

    🔴 비운영에서 미기동 — TestClient 가 lifespan 을 돌릴 때 백그라운드 태스크가 뜨면
    단위 테스트가 비결정적이 된다.
    """
    return bool(settings.is_production) and not settings.scheduler_disabled


# ── job 본문 (엔드포인트와 동일 세션 패턴) ───────────────────────────────
# Job bodies — same session pattern as the internal cron endpoints


async def _retry_pending_merges():
    settings = Settings()
    with SessionLocal() as db:
        counts = await process_pending_retries(db, limit=settings.merge_retry_worker_batch_size)
    logger.info("scheduler retry_pending_merges: counts=%s", counts)


async def _sweep_orphans():
    with SessionLocal() as db:
        surfaced = await sweep_analysis_attempts(db)
    logger.info("scheduler sweep_orphans: surfaced=%d", surfaced)


async def _retention_sweep():
    with SessionLocal() as db:
        counts = run_retention_sweep(db)
    logger.info("scheduler retention_sweep: counts=%s", counts)


async def _trend_check():
    with SessionLocal() as db:
        sent = await run_trend_check(db)
    logger.info("scheduler trend_check: sent=%s", sent)


async def _weekly_reports():
    with SessionLocal() as db:
        sent = await run_weekly_reports(db)
    logger.info("scheduler weekly_reports: sent=%s", sent)


async def _scan_security():
    """GHAS Code/Secret Scanning alert 폴링 — 2026-07-19 사용자 결정으로 활성화.
    GHAS alert polling; enabled by user decision on 2026-07-19.

    🔴 이 job 은 **출시 이래 스케줄되지 않았다**(엔드포인트만 존재). 파리티 가드
    (`tests/unit/test_cron_scheduler_parity.py`)가 그 갭을 표면화해 결정으로 이어졌다.
    긴급 차단은 `SECURITY_AUTO_PROCESS_DISABLED=1` kill-switch.
    """
    with SessionLocal() as db:
        totals = await scan_all_repos(db)
    logger.info("scheduler scan_security: totals=%s", totals)


# 🔴 구 railway.toml `[[deploy.cronJobs]]` 5종과 **동일 주기** — 값 변경은 운영 동작 변경이다.
# Same schedules as the (inert) railway.toml cron blocks; guarded by tests.
JOBS = (
    Job("retry-pending-merges", _retry_pending_merges, every_seconds=60),        # * * * * *
    Job("sweep-orphans", _sweep_orphans, every_seconds=600),                     # */10 * * * *
    Job("trend", _trend_check, daily_at=(3, 0)),                                 # 0 3 * * *
    Job("retention-sweep", _retention_sweep, daily_at=(20, 0)),                  # 0 20 * * *
    Job("weekly-reports", _weekly_reports, weekly_at=(0, 0, 0)),                 # 0 0 * * 1
    Job("scan-security", _scan_security, daily_at=(4, 0)),                       # 0 4 * * *
)


# 🔴 cron 엔드포인트 경로 ↔ JOBS job 이름 매핑 (**단일 출처**).
# 이름이 다른 쌍이 있으므로(`weekly` ↔ `weekly-reports`) 테스트에 복제하면 drift 한다.
# Single source of truth for endpoint-path → job-name (some names differ; never duplicate this
# mapping into a test).
CRON_PATH_TO_JOB = {
    "weekly": "weekly-reports",
    "trend": "trend",
    "retry-pending-merges": "retry-pending-merges",
    "sweep-orphans": "sweep-orphans",
    "retention-sweep": "retention-sweep",
    "scan-security": "scan-security",
}

# 🔴 의도적으로 주기 실행하지 **않는** cron 경로 → 사유 (2026-07-19 회고 P1).
# 사유를 주석이 아니라 **값**으로 두는 이유: 주석은 검증할 수 없어 "왜 예외인지 아무도 기억
# 못 하는" 상태로 부패한다. `test_every_unscheduled_path_documents_its_reason` 가 강제한다.
# Reasons live as values, not comments — a comment cannot be enforced and decays.
#
# 🔴 이 목록이 존재하는 진짜 이유: `scan-security` 는 엔드포인트가 있는데 스케줄러 job 이 없어
# **출시 이래 주기 실행 0회**였고, 문서는 실행된다고 단언했다 — 2026-07-19 P0(Railway cron 5종
# 전면 미실행)과 **정확히 같은 실패 모드**다. 파리티 가드가 이 갭을 구조로 고정한다.
# 🔴 현재 비어 있다 — 2026-07-19 사용자 결정으로 `scan-security` 가 활성화되어 6종 전부 스케줄된다.
# 빈 dict 를 남겨두는 이유: 향후 미스케줄 엔드포인트가 생기면 **여기 등재가 강제**되고
# (파리티 가드가 CI FAIL), 사유를 값으로 남기게 된다.
# Intentionally empty — every cron path is scheduled as of 2026-07-19. Kept so any future
# unscheduled endpoint must be registered here with a reason (the parity guard enforces it).
UNSCHEDULED_CRON_PATHS = {}


def _seconds_until_next(job, now):
    """다음 실행까지 남은 초 — 스케줄 종류별 계산.
    Seconds until this job's next run."""
    if job.every_seconds is not None:
        return job.every_seconds
    if job.daily_at is not None:
        return (next_daily_run(now, *job.daily_at) - now).total_seconds()
    return (next_weekly_run(now, *job.weekly_at) - now).total_seconds()


async def _run_job_forever(job):
    """단일 job 루프 — 실행 실패가 루프를 죽이지 않는다(다음 주기 계속).
    Per-job loop; a failing run must never kill the loop."""
    while True:
        delay = _seconds_until_next(job, datetime.now(timezone.utc))
        await asyncio.sleep(delay)
        try:
            await job.run()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — job 격리: 어떤 실패도 스케줄러를 멈추지 않는다
            logger.exception("scheduler job failed: %s", job.name)


def start(settings):
    """스케줄러 기동 → 생성된 태스크 목록(미기동 시 빈 목록).
    Start the scheduler; returns the created tasks (empty when disabled)."""
    if not scheduler_enabled(settings):
        logger.info("scheduler disabled (production=%s)", settings.is_production)
        return []
    tasks = [asyncio.create_task(_run_job_forever(j), name=f"scheduler:{j.name}") for j in JOBS]
    logger.info("scheduler started — %d jobs: %s", len(tasks), ", ".join(j.name for j in JOBS))
    return tasks


async def stop(tasks):
    """스케줄러 정지 — 태스크 취소 후 정리 대기.
    Cancel scheduler tasks and await their teardown."""
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001 — 종료 경로는 조용히
            pass  # 종료 중 예외는 무시 / ignore teardown errors
