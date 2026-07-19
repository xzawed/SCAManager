"""런타임 부팅 관측 가드 — lifespan 이 **실제로 무엇을 했는가** 를 단언한다 (2026-07-19 회고 P1).
Runtime boot smoke guard: asserts what the real lifespan actually did.

🔴 왜 필요한가 / why this exists:
가드 포트폴리오 12종이 전부 **정적·저장소-내 분석**이라 "부팅 시 관측 가능한 상태" 를 단언하는
가드가 하나도 없었다. 그 결과:
  - #1100(`configure_logging()`)이 **테스트 통과 상태로 운영에서 무력**했다 — lifespan 이
    인프로세스로 마이그레이션을 돌리고, alembic 의 `fileConfig` 가 앱 로깅을 통째로 되돌렸다.
  - 인앱 스케줄러(#1099) 배선 갭도 부팅 관측이 없어 못 잡았다.
Every existing guard was static/in-repo analysis, so a fix could pass tests and still be inert in
production. These tests enter the real lifespan and assert observable runtime state.

🔴 이 파일의 설계 원칙 / design rules:
  1. **실제 `src.main.lifespan` 을 진입**한다 (mock 된 대역 lifespan 금지).
  2. **`_run_migrations` patch 는 "alembic 이 로깅을 재설정한다" 는 성질을 재현**해야 한다.
     단순 `MagicMock()` 로 갈음하면 #1102 회귀를 **구조적으로 못 잡는다** — 그래서 이 파일의
     대역은 **진짜 `alembic/env.py` 를 in-process 로 exec** 한다(`command.current`, DB 는
     in-memory SQLite). `alembic/env.py` 의 `is_configured()` 가드를 제거하면 아래 로깅
     테스트들이 FAIL 한다(뮤테이션 실증 완료).
  3. 실 DB·네트워크 접촉 0 — 마이그레이션 URL 은 `sqlite://`, HTTP 클라이언트/warm-up 은 patch.
  4. **스케줄러 태스크 누출 금지** — lifespan 종료 후 살아있는 태스크가 없음을 단언한다.
  5. 전역 logging 격리는 `tests/unit/conftest.py::logging_isolation` (opt-in) 사용 의무.
"""
import asyncio
import logging
import pathlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.logging_config import _MARKER, configure_logging
from src.main import app, lifespan
from src.models.repository import Repository

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"

# 운영에서 실제로 죽었던 로거 / the loggers that actually went silent in production
_APP_LOGGER = "src.scheduler"
_ACCESS_LOGGER = "uvicorn.access"

# 스케줄러가 태스크에 붙이는 이름 접두사 (`scheduler.start`: name=f"scheduler:{job.name}").
# The task-name prefix scheduler.start() assigns; used to observe boot from the event loop.
_TASK_PREFIX = "scheduler:"

# main.py lifespan 이 마이그레이션 성공 시 남기는 라인 / logged by lifespan after migrations
_MIGRATION_DONE_LINE = "DB migration completed"
# scheduler.start() 가 기동 시 남기는 라인 / logged by scheduler.start() on startup
_SCHEDULER_START_LINE = "scheduler started"


class _RecordCollector(logging.Handler):
    """root 에 붙여 부팅 중 발생한 레코드를 그대로 모으는 관측 핸들러.
    An observation handler attached to root that collects records emitted during boot.

    🔴 caplog 대신 자체 핸들러를 쓰는 이유: 이 파일은 **로깅 파괴 여부 자체**를 검증한다.
    alembic 의 `_clearExistingHandlers()` 가 root 핸들러를 비우면 이 핸들러도 함께 사라져
    이후 라인이 수집되지 않는다 — 그것이 바로 우리가 잡으려는 신호다. caplog 는 pytest 가
    별도 시점에 붙였다 떼므로 이 신호를 흐린다.
    Using our own handler (not caplog) is deliberate: if fileConfig wipes root handlers this
    handler disappears too and later lines go uncollected — exactly the signal under test.
    """

    def __init__(self):
        super().__init__(level=logging.NOTSET)
        self.records = []

    def emit(self, record):
        self.records.append(record)

    def has_line(self, needle: str) -> bool:
        """수집된 레코드 중 needle 을 포함하는 메시지가 있는지 / whether any message contains needle."""
        for record in self.records:
            try:
                message = record.getMessage()
            except (TypeError, ValueError):  # pragma: no cover — 포맷 인자 불일치 방어
                continue
            if needle in message:
                return True
        return False

    def dump(self) -> str:
        """실패 메시지용 요약 — 예외 레코드는 트레이스백까지 포함한다.
        Compact summary for assertion messages; exception records include the traceback.

        🔴 트레이스백을 반드시 실어야 한다 — `lifespan` 은 마이그레이션 실패를
        `logger.exception("DB migration failed")` 로 **삼키고 기동을 계속**하므로, 메시지만
        보면 "왜 실패했는지" 가 사라져 진단이 불가능해진다.
        The lifespan swallows migration failures, so without exc_info the cause is unrecoverable.
        """
        lines = []
        for record in self.records:
            lines.append(f"  [{record.name}] {record.getMessage()}")
            if record.exc_info:
                trace = logging.Formatter().formatException(record.exc_info)
                lines.extend(f"      {ln}" for ln in trace.splitlines())
        return "\n".join(lines) or "  (수집 0건)"


def _exec_real_alembic_env() -> None:
    """`_run_migrations` 대역 — **진짜 `alembic/env.py`** 를 in-process 로 실행한다.
    Stand-in for _run_migrations that executes the real alembic/env.py in-process.

    🔴 이 대역이 이 파일의 핵심이다. `MagicMock()` 로 갈음하면 "마이그레이션이 앱 로깅을
    파괴하는가" 라는 질문 자체가 사라져 #1102 회귀를 영원히 못 잡는다. `command.current` 는
    리비전을 **조회만** 하므로 env.py 모듈 레벨 코드(= `fileConfig` 가드 지점)만 통과한다.
    Using a MagicMock would delete the very question under test; command.current runs env.py's
    module-level code (where the fileConfig guard lives) without applying any migration.
    """
    # 지연 import — 수집 시점에 alembic 이 로깅을 건드리지 않게 한다.
    # Local import so alembic cannot touch logging at collection time.
    from alembic import command  # pylint: disable=import-outside-toplevel
    from alembic.config import Config  # pylint: disable=import-outside-toplevel

    cfg = Config(str(_ALEMBIC_INI))
    # script_location 은 ini 에 상대경로로 적혀 cwd 에 의존한다 — 절대경로로 고정.
    # script_location is cwd-dependent in the ini; pin it to an absolute path.
    cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    command.current(cfg)


def _orm_declarative_base():
    """ORM 클래스들이 **실제로** 등록돼 있는 declarative Base 를 돌려준다.
    The declarative Base the ORM classes are actually registered against.

    🔴 왜 필요한가 (테스트 전용 아티팩트 복구): `tests/unit/test_database.py` ·
    `test_failover.py` 의 헬퍼가 `importlib.reload(src.database)` 를 호출하고 **복원하지 않는다**.
    reload 는 `Base = declarative_base()` 를 재실행해 **빈 metadata 를 가진 새 Base** 를 만드는데,
    `sys.modules` 에 캐시된 13개 모델 클래스는 여전히 **옛 Base** 에 바인딩돼 있다. 그 결과
    이후 세션 내내 `src.database.Base.metadata.tables` 가 비어, `alembic/env.py` 의
    `_REGISTERED_MODELS` 완전성 가드가 13종 전부를 "미등록" 으로 보고 RuntimeError 를 던진다
    (알파벳 순으로 이 파일이 그 두 파일 뒤에 오므로 전체 스위트에서만 재현됐다).
    Those helpers reload src.database without restoring it, leaving the cached model classes bound
    to the old Base — so env.py's completeness guard sees every model as unregistered.

    🔴 운영에서는 reload 가 없어 `src.database.Base` 와 모델 바인딩이 **항상 일치**한다. 즉 이
    복구는 운영 결함을 가리는 것이 아니라 **테스트 프로세스에만 존재하는 왜곡을 되돌린다**.
    Production never reloads, so this restores a test-only distortion rather than masking a defect.
    """
    for klass in Repository.__mro__[1:]:
        if getattr(klass, "metadata", None) is Repository.metadata:
            return klass
    raise RuntimeError(  # pragma: no cover — declarative 관례가 깨진 경우에만 도달
        "ORM 모델의 declarative Base 를 찾지 못했다 — SQLAlchemy 선언 방식이 바뀌었나?"
    )


@pytest.fixture
def boot_env(monkeypatch, logging_isolation):  # pylint: disable=unused-argument
    """부팅 대역 환경 — 실 DB·네트워크 0, 마이그레이션은 진짜 env.py 실행.
    Boot harness: no real DB or network, but the migration step runs the real env.py.

    반환값 / returns: 부팅 중 로그를 모으는 `_RecordCollector`.

    🔴 patch 는 전부 **string-path** 로 한다 (testing.md). 다른 테스트가
    `importlib.reload(src.config)` / `reload(src.main)` 을 호출하면 모듈 속성이 **새 객체**로
    바뀌는데, 모듈 최상단에서 import 해 둔 객체를 patch 하면 lifespan 이 보는 객체와 어긋나
    조용히 무효가 된다. string-path 는 호출 시점에 현재 객체를 해석한다.
    All patches use string paths so they bind to whatever object the lifespan currently sees,
    even after another test reloaded src.config / src.main.
    """
    # 🔴 alembic/env.py 는 cfg 의 sqlalchemy.url 을 settings.effective_migration_url 로 **무조건
    # override** 하므로 cfg 만 설정하면 무효다 (.claude/rules/db.md) — settings 싱글톤을 patch.
    # env.py always overrides cfg's URL with settings.effective_migration_url — patch the singleton.
    monkeypatch.setattr("src.config.settings.database_url", "sqlite://")
    monkeypatch.setattr("src.config.settings.migration_database_url", "")

    # 앞선 테스트의 reload 로 어긋난 Base ↔ 모델 바인딩을 운영과 동일한 상태로 되돌린다.
    # Restore the Base↔model binding that an earlier test's reload may have broken.
    monkeypatch.setattr("src.database.Base", _orm_declarative_base())

    # 마이그레이션 = 진짜 env.py (로깅 재설정 성질 재현) / real env.py, reproducing the logging reset
    monkeypatch.setattr("src.main._run_migrations", _exec_real_alembic_env)

    # HTTP 클라이언트 + GitHub warm-up ping — 네트워크 접촉 0
    # HTTP client + GitHub warm-up ping — zero network contact
    monkeypatch.setattr("src.main.init_http_client", AsyncMock())
    monkeypatch.setattr("src.main.close_http_client", AsyncMock())
    warmup_client = MagicMock()
    warmup_client.get = AsyncMock()
    monkeypatch.setattr(
        "src.shared.http_client.get_http_client", MagicMock(return_value=warmup_client)
    )

    # 운영과 동일하게 로거 인스턴스를 미리 생성 — `disable_existing_loggers` 는 **이미 존재하는**
    # 로거만 disable 하므로, 이 전제가 없으면 사고가 재현되지 않는다.
    # Materialize loggers first: disable_existing_loggers only touches loggers that already exist.
    logging.getLogger(_APP_LOGGER)
    logging.getLogger(_ACCESS_LOGGER)

    configure_logging()

    collector = _RecordCollector()
    logging.getLogger().addHandler(collector)
    yield collector
    logging.getLogger().removeHandler(collector)


def _production(monkeypatch) -> None:
    """운영 조건 — `ENVIRONMENT=production` + kill-switch off (= SCHEDULER_DISABLED 미설정 기본값).
    Production condition: explicit production signal with the scheduler kill-switch off.

    🔴 `is_production` 은 프로퍼티라 직접 대입할 수 없다 — 실제 판정 입력(`environment`)을 바꿔
    **진짜 `is_production` 로직을 통과**시킨다 (판정을 우회하면 가드가 약해진다).
    is_production is a property; we set its real input rather than stubbing the verdict.

    🔴 대상은 `src.main.settings` — `scheduler.start(settings)` 에 넘어가는 바로 그 객체다.
    Targets src.main.settings: the exact object handed to scheduler.start().
    """
    monkeypatch.setattr("src.main.settings.environment", "production")
    monkeypatch.setattr("src.main.settings.scheduler_disabled", False)


def _live_scheduler_tasks() -> list:
    """현재 이벤트 루프에 살아있는 스케줄러 태스크 / live scheduler tasks on this loop."""
    return [t for t in asyncio.all_tasks() if (t.get_name() or "").startswith(_TASK_PREFIX)]


# --------------------------------------------------------------------------------------
# 1. 부팅 관측 — 로그가 실제로 도달하는가 / boot observability: do the lines actually arrive?
# --------------------------------------------------------------------------------------

async def test_migration_completed_line_reaches_the_log(boot_env):
    """🔴 마이그레이션 후 `DB migration completed` 가 실제로 로그에 도달한다 (#1102 회귀 봉인).

    이 라인은 마이그레이션 **이후**에 찍힌다. alembic 의 fileConfig 가 root 핸들러를 비우면
    (구 동작) 이 라인이 어디에도 도달하지 않는다 — 운영에서 정확히 그 일이 있었다.
    """
    async with lifespan(app):
        pass

    assert boot_env.has_line(_MIGRATION_DONE_LINE), (
        f"lifespan 진입 후 {_MIGRATION_DONE_LINE!r} 라인이 로그에 도달하지 않았다.\n"
        "→ 인프로세스 마이그레이션이 앱 로깅을 파괴했다 (alembic/env.py 의 fileConfig 가드 회귀).\n"
        f"수집된 레코드:\n{boot_env.dump()}"
    )


async def test_scheduler_start_line_reaches_the_log(boot_env, monkeypatch):
    """🔴 운영 조건에서 스케줄러 기동 로그가 실제로 도달한다 — #1099 배포 검증의 전제.

    `scheduler started — N jobs` 가 보이지 않아 인앱 스케줄러 배포 검증이 3세션째 막혔던
    사고를 봉인한다.
    """
    _production(monkeypatch)

    async with lifespan(app):
        pass

    assert boot_env.has_line(_SCHEDULER_START_LINE), (
        f"운영 조건 부팅인데 {_SCHEDULER_START_LINE!r} 라인이 로그에 도달하지 않았다.\n"
        "→ 스케줄러가 기동하지 않았거나, 마이그레이션이 앱 로깅을 파괴해 라인이 소실됐다.\n"
        f"수집된 레코드:\n{boot_env.dump()}"
    )


# --------------------------------------------------------------------------------------
# 2. 로깅 설정이 lifespan 통과 후에도 유지되는가 / logging config survives the whole lifespan
# --------------------------------------------------------------------------------------

async def test_root_level_stays_info_after_lifespan(boot_env):  # pylint: disable=unused-argument
    """🔴 lifespan 통과 후에도 root level 이 INFO — alembic.ini 의 `level = WARN` 이 이기면 안 된다."""
    async with lifespan(app):
        pass

    assert logging.getLogger().level == logging.INFO, (
        "lifespan 통과 후 root level 이 INFO 가 아님 "
        f"(현재: {logging.getLevelName(logging.getLogger().level)}) — "
        "alembic.ini [logger_root] level=WARN 이 앱 로깅을 덮어썼다. 앱 INFO 로그가 전부 소실된다."
    )


async def test_app_handler_survives_lifespan(boot_env):  # pylint: disable=unused-argument
    """🔴 우리 stdout 핸들러(`_MARKER`)가 root 에 생존 — alembic stderr 핸들러로 교체 금지."""
    async with lifespan(app):
        pass

    root = logging.getLogger()
    assert any(getattr(h, _MARKER, False) for h in root.handlers), (
        f"lifespan 통과 후 앱 핸들러(_MARKER)가 root 에서 사라짐 (현재: {root.handlers}) — "
        "fileConfig 의 _clearExistingHandlers 가 제거했다."
    )


async def test_app_logger_still_emits_info_after_lifespan(boot_env):  # pylint: disable=unused-argument
    """🔴 `src.scheduler` 가 lifespan 이후에도 INFO 를 통과시킨다."""
    async with lifespan(app):
        pass

    assert logging.getLogger(_APP_LOGGER).isEnabledFor(logging.INFO), (
        f"lifespan 통과 후 {_APP_LOGGER} 가 INFO 를 못 통과시킴 — "
        "disable_existing_loggers 가 적용됐다. 운영 관측 라인이 다시 전부 사라진다."
    )


async def test_uvicorn_access_logger_not_disabled_after_lifespan(boot_env):  # pylint: disable=unused-argument
    """🔴 `uvicorn.access` 가 disabled 되지 않는다 — access 로그 24h 0건 사고의 직접 원인."""
    async with lifespan(app):
        pass

    assert not logging.getLogger(_ACCESS_LOGGER).disabled, (
        f"lifespan 통과 후 {_ACCESS_LOGGER} 가 disabled — fileConfig 의 "
        "disable_existing_loggers=True 가 적용됐다. uvicorn access 로그가 전부 사라진다."
    )


# --------------------------------------------------------------------------------------
# 3. 스케줄러가 실제로 기동/정지하는가 / does the scheduler actually start and stop?
# --------------------------------------------------------------------------------------

async def test_production_boot_creates_one_task_per_job(boot_env, monkeypatch):  # pylint: disable=unused-argument
    """🔴 운영 부팅이 job 수만큼 태스크를 **실제로 생성**한다 — 이벤트 루프에서 직접 관측.

    `scheduler.start` 반환값이 아니라 `asyncio.all_tasks()` 를 본다: lifespan 이 반환값을
    버리거나 stop 에 넘기지 않는 배선 실수까지 잡기 위함이다.
    Observes the event loop (not start()'s return value) so a lost-wiring mistake is also caught.
    """
    from src.scheduler import JOBS  # pylint: disable=import-outside-toplevel

    _production(monkeypatch)

    async with lifespan(app):
        live = _live_scheduler_tasks()
        names = sorted((t.get_name() or "") for t in live)

    assert len(live) == len(JOBS), (
        f"운영 부팅인데 스케줄러 태스크가 {len(live)}개 (기대: {len(JOBS)}) — {names}\n"
        "→ lifespan 이 scheduler.start(settings) 를 호출하지 않았거나 job 등록이 누락됐다."
    )
    assert names == sorted(f"{_TASK_PREFIX}{j.name}" for j in JOBS), (
        f"기동된 태스크 이름이 JOBS 와 불일치: {names}"
    )


async def test_non_production_boot_creates_no_tasks(boot_env, monkeypatch):  # pylint: disable=unused-argument
    """🔴 비운영 부팅은 태스크를 하나도 만들지 않는다 — TestClient lifespan 이 백그라운드 태스크를
    띄우면 단위 테스트 수천 건이 비결정적이 된다."""
    monkeypatch.setattr("src.main.settings.environment", "")
    monkeypatch.setattr("src.main.settings.app_base_url", "")

    async with lifespan(app):
        live = _live_scheduler_tasks()

    assert not live, (
        f"비운영 부팅인데 스케줄러 태스크가 생성됨: {[t.get_name() for t in live]} — "
        "scheduler_enabled 의 is_production 가드가 무력화됐다."
    )


async def test_scheduler_tasks_do_not_leak_after_lifespan(boot_env, monkeypatch):  # pylint: disable=unused-argument
    """🔴 lifespan 종료 후 스케줄러 태스크가 남지 않는다 — 테스트/운영 양쪽 누수 차단.

    `finally: await scheduler.stop(...)` 가 빠지면 태스크가 루프에 영구 잔류해
    뒤따르는 테스트를 오염시키고, 운영에서는 재기동 시 중복 실행이 된다.
    """
    _production(monkeypatch)

    async with lifespan(app):
        started = _live_scheduler_tasks()
        assert started, "전제 실패 — 운영 부팅인데 태스크가 하나도 없어 누수 단언이 공허하다"

    assert all(t.done() for t in started), (
        f"lifespan 종료 후에도 끝나지 않은 스케줄러 태스크 존재: "
        f"{[t.get_name() for t in started if not t.done()]} — scheduler.stop() 미호출/미대기."
    )
    assert not _live_scheduler_tasks(), (
        f"lifespan 종료 후 루프에 스케줄러 태스크 잔류: "
        f"{[t.get_name() for t in _live_scheduler_tasks()]}"
    )
