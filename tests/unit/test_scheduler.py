"""인앱 스케줄러 정합 (2026-07-19 P0 — Railway cron 미실행 사고 봉인).

🔴 사고: `railway.toml` 의 `[[deploy.cronJobs]]` 는 **Railway 스키마에 존재하지 않는 키**라
조용히 무시됐다. Railway cron 은 서비스당 **단일 `cronSchedule`**(대시보드 또는 config-as-code
`deploy.cronSchedule`)이며 배열을 지원하지 않는다. 실측: SCAManager 서비스 `cronSchedule=null`
· `nextCronRunAt=null` → weekly/trend/retry/orphan/retention **5종 전부 한 번도 실행 안 됨**.
결정적 증거 = 20:00 UTC 스윕 3.5시간 경과 후에도 만료 캐시 8건 잔존(`purge_expired` 는
`expires_at < now` 를 지우므로 실행됐다면 0이어야 함).
Incident: `[[deploy.cronJobs]]` is not a Railway config key — silently ignored. All 5 crons had
never run. Replaced with an in-app scheduler so wiring is asserted by tests, not invisible config.

🔴 순수 시각 계산만 테스트 — 실제 sleep/task 기동은 단언하지 않는다(flaky).
Pure scheduling math only; the running loop itself is not asserted (would flake).
"""
from datetime import datetime, timezone

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


def test_all_five_cron_jobs_registered():
    """🔴 railway.toml 이 무음으로 잃었던 5종이 전부 등록 — 배선을 테스트로 단언.

    이번 사고의 근본은 '설정이 저장소 밖에 있어 어긋나도 아무도 모른다' 였다.
    """
    names = {j.name for j in JOBS}
    assert names == {
        "retry-pending-merges", "sweep-orphans", "trend", "retention-sweep", "weekly-reports",
    }, f"등록 누락/오타: {names}"


def test_job_schedules_match_previous_cron_expressions():
    """🔴 구 railway.toml 스케줄과 동일 — 주기가 조용히 바뀌면 운영 동작이 달라진다."""
    by_name = {j.name: j for j in JOBS}
    assert by_name["retry-pending-merges"].every_seconds == 60          # * * * * *
    assert by_name["sweep-orphans"].every_seconds == 600                # */10 * * * *
    assert by_name["trend"].daily_at == (3, 0)                          # 0 3 * * *
    assert by_name["retention-sweep"].daily_at == (20, 0)               # 0 20 * * *
    assert by_name["weekly-reports"].weekly_at == (0, 0, 0)             # 0 0 * * 1 (월 00:00)


def test_every_job_has_exactly_one_schedule_kind():
    """각 job 은 interval/daily/weekly 중 정확히 하나 — 중복 지정 시 동작 모호."""
    for job in JOBS:
        kinds = [job.every_seconds is not None, job.daily_at is not None, job.weekly_at is not None]
        assert sum(kinds) == 1, f"{job.name}: 스케줄 종류 {sum(kinds)}개"


def test_every_job_is_callable():
    """🔴 job 이 실제 호출 가능한 함수를 물고 있어야 한다 — 이름만 있으면 dead 배선."""
    for job in JOBS:
        assert callable(job.run), f"{job.name}: run 이 호출 불가"
