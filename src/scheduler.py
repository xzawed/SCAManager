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


# 🔴 구 railway.toml `[[deploy.cronJobs]]` 5종과 **동일 주기** — 값 변경은 운영 동작 변경이다.
# Same schedules as the (inert) railway.toml cron blocks; guarded by tests.
JOBS = (
    Job("retry-pending-merges", _retry_pending_merges, every_seconds=60),        # * * * * *
    Job("sweep-orphans", _sweep_orphans, every_seconds=600),                     # */10 * * * *
    Job("trend", _trend_check, daily_at=(3, 0)),                                 # 0 3 * * *
    Job("retention-sweep", _retention_sweep, daily_at=(20, 0)),                  # 0 20 * * *
    Job("weekly-reports", _weekly_reports, weekly_at=(0, 0, 0)),                 # 0 0 * * 1
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
}

# 🔴 의도적으로 주기 실행하지 **않는** cron 경로 → 사유 (2026-07-19 회고 P1).
# 사유를 주석이 아니라 **값**으로 두는 이유: 주석은 검증할 수 없어 "왜 예외인지 아무도 기억
# 못 하는" 상태로 부패한다. `test_every_unscheduled_path_documents_its_reason` 가 강제한다.
# Reasons live as values, not comments — a comment cannot be enforced and decays.
#
# 🔴 이 목록이 존재하는 진짜 이유: `scan-security` 는 엔드포인트가 있는데 스케줄러 job 이 없어
# **출시 이래 주기 실행 0회**였고, 문서는 실행된다고 단언했다 — 2026-07-19 P0(Railway cron 5종
# 전면 미실행)과 **정확히 같은 실패 모드**다. 파리티 가드가 이 갭을 구조로 고정한다.
UNSCHEDULED_CRON_PATHS = {
    "scan-security": (
        "GHAS 폴링(scan_all_repos)은 GitHub API 쿼터를 소모하고 알림을 발생시키므로 "
        "주기 실행 활성화는 사용자 결정 영역(정책 15 High tier). 현재는 수동/외부 트리거 전용."
    ),
}


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
        # pylint: disable=try-except-raise
        # W0706 의도적 — 아래 `except Exception` 이 취소까지 삼키는 것을 막는 **순서 장치**다.
        # 이 분기를 지우면 stop() 의 task.cancel() 이 job 격리 핸들러에 먹혀 종료가 멈춘다.
        # Intentional: this arm exists so the broad handler below cannot swallow cancellation.
        except asyncio.CancelledError:
            raise
        # pylint: disable=broad-exception-caught
        # W0718 의도적 — job 격리. 어떤 job 의 어떤 실패도 스케줄러 루프를 멈춰선 안 된다.
        # Intentional: job isolation — no job's failure may kill the scheduler loop.
        except Exception:  # noqa: BLE001
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
        # pylint: disable=broad-exception-caught
        # W0718 의도적 — 종료 경로에서 한 job 의 예외가 **나머지 job 의 정리를 막으면 안 된다**.
        # `CancelledError` 는 3.8+ 에서 BaseException 상속이라 `Exception` 과 함께 명시해야 둘 다 잡힌다.
        # Intentional: during teardown, one job's exception must not block cleanup of the others.
        # CancelledError derives from BaseException (3.8+), so both must be listed explicitly.
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass  # 종료 중 예외는 무시 / ignore teardown errors
