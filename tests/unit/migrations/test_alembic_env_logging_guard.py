"""alembic/env.py 의 `fileConfig` 가 앱 로깅을 파괴하지 않는지 잠그는 회귀 가드.
Regression guard: alembic/env.py's fileConfig must not destroy application logging.

🔴 사고 (2026-07-19): #1100 이 `configure_logging()` 으로 앱 INFO 로그를 살렸으나 **운영에서는
무력**했다. 앱 lifespan 이 인프로세스로 마이그레이션을 돌리기 때문이다:
  src/main.py lifespan → asyncio.to_thread(_run_migrations) → command.upgrade(Config("alembic.ini"))
  → alembic 이 alembic/env.py 를 exec → `fileConfig(config.config_file_name)`
`logging.config.fileConfig()` 는 기본값 `disable_existing_loggers=True` 이고 alembic.ini 는
`[logger_root] level = WARN` + `[handler_console] args = (sys.stderr,)` 이므로, 이미 설정된
앱 로깅이 통째로 덮어써진다. 로컬 재현 실측:

  | 항목                                   | fileConfig 이전  | 이후                   |
  |----------------------------------------|------------------|------------------------|
  | root level                             | INFO             | WARNING                |
  | root handlers                          | 우리 것(stdout)  | alembic 것(stderr)     |
  | `uvicorn.access` `.disabled`           | False            | True                   |
  | `src.scheduler.isEnabledFor(INFO)`     | True             | False                  |

운영 영향: 앱 INFO 로그 전부 소실 + uvicorn access 로그 24h 0건 → 인앱 스케줄러(#1099) 배포
검증이 3세션째 불가능.

계약 / contract: env.py 는 **앱이 이미 로깅을 설정한 경우(=인프로세스 마이그레이션)** fileConfig
를 건너뛰고, **앱이 설정하지 않은 경우(=`make migrate` 등 alembic CLI 단독 실행)** 는 기존대로
호출해 CLI 로그를 보존한다.

🔴 산문 검사 금지 — 이 파일은 env.py 소스에서 "is_configured" 문자열을 grep 하지 않는다.
`alembic.command.current` 로 **실제 env.py 를 in-process exec** 해 관측 가능한 로깅 상태를
단언한다. 가드를 제거하면(=무조건 fileConfig 호출) 아래 test_app_logging_survives_* 가 FAIL 한다.
🔴 No prose assertions: this exercises the real env.py via alembic.command.current and asserts the
observable logging state, so removing the guard makes these tests fail.
"""
import logging
import logging.config
import pathlib

import pytest

from src.logging_config import _MARKER, configure_logging

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_ALEMBIC_INI = _REPO_ROOT / "alembic.ini"

# 운영에서 실제로 죽었던 로거들 — fileConfig 의 disable_existing_loggers 사정권.
# The loggers that actually went silent in production; in range of disable_existing_loggers.
_APP_LOGGER = "src.scheduler"
_ACCESS_LOGGER = "uvicorn.access"


@pytest.fixture(autouse=True)
def _isolate(logging_isolation):
    """이 파일의 모든 테스트에 전역 logging 격리를 강제한다 (요청 누락 방지).
    Force global logging isolation on every test in this file so none can forget to ask for it.
    """


@pytest.fixture(autouse=True)
def _ephemeral_migration_db(monkeypatch):
    """마이그레이션 URL 을 in-memory SQLite 로 고정 — 실 DB 접촉 0.
    Pin the migration URL to in-memory SQLite so no real database is ever touched.

    🔴 alembic/env.py 는 cfg 의 `sqlalchemy.url` 을 `settings.effective_migration_url` 로 **무조건
    override** 하므로 cfg 만 설정하면 무효다 (.claude/rules/db.md) — settings 싱글톤을 patch 한다.
    🔴 env.py always overrides cfg's sqlalchemy.url with settings.effective_migration_url, so the
    settings singleton (not the cfg) is what must be patched.
    """
    monkeypatch.setattr("src.config.settings.database_url", "sqlite://")
    monkeypatch.setattr("src.config.settings.migration_database_url", "")


def _materialize_runtime_loggers() -> None:
    """운영과 동일하게 로거 인스턴스를 미리 생성한다.
    Materialize logger instances exactly as production does before migrations run.

    `disable_existing_loggers` 는 **이미 존재하는** 로거만 disable 한다. 운영에서는 uvicorn 이
    startup 에서 access 로거를, 앱 모듈이 import 시점에 `src.*` 로거를 이미 만들어 둔 상태로
    lifespan 마이그레이션에 진입하므로, 테스트도 같은 전제를 만들어야 사고가 재현된다.
    disable_existing_loggers only touches loggers that already exist, so the test must create them
    first — as uvicorn and the app modules do before lifespan runs.
    """
    logging.getLogger(_APP_LOGGER)
    logging.getLogger(_ACCESS_LOGGER)


def _run_alembic_env() -> None:
    """alembic/env.py 를 실제로 in-process 실행한다.
    Actually execute alembic/env.py in-process.

    `command.current` 는 리비전 **조회만** 하고 마이그레이션을 적용하지 않으므로, env.py 모듈
    레벨 코드(= fileConfig 가드 지점)만 빠르게 통과한다 (실측 ~0.5s).
    command.current only reads the current revision, so it runs env.py's module-level code — where
    the fileConfig guard lives — without applying migrations (~0.5s measured).
    """
    # 지연 import — 모듈 import 시점에 alembic 이 로깅을 건드리지 않게 한다.
    # Local import so alembic cannot touch logging at collection time.
    from alembic import command  # pylint: disable=import-outside-toplevel
    from alembic.config import Config  # pylint: disable=import-outside-toplevel

    cfg = Config(str(_ALEMBIC_INI))
    # script_location 은 ini 에 상대경로("alembic")로 적혀 cwd 에 의존한다 — 절대경로로 고정.
    # script_location is relative in the ini and thus cwd-dependent; pin it to an absolute path.
    cfg.set_main_option("script_location", str(_REPO_ROOT / "alembic"))
    command.current(cfg)


def _strip_app_logging() -> None:
    """앱 로깅 미설정 상태를 만든다 (= alembic CLI 단독 실행 상황).
    Produce the "app never configured logging" state (i.e. standalone alembic CLI).

    conftest 가 `src.main` 을 import 하면서 이미 `configure_logging()` 이 호출돼 있으므로,
    CLI 경로를 검증하려면 marker 핸들러를 명시적으로 걷어내야 한다.
    Importing src.main in conftest already ran configure_logging(), so the marker handler must be
    removed explicitly to exercise the CLI path.
    """
    root = logging.getLogger()
    root.handlers[:] = [h for h in root.handlers if not getattr(h, _MARKER, False)]


# --------------------------------------------------------------------------------------
# 핵심 회귀 가드 / core regression guard
# --------------------------------------------------------------------------------------

def test_app_logging_survives_in_process_migration():
    """🔴 앱이 로깅을 설정한 뒤 마이그레이션을 돌려도 root level 이 INFO 로 살아남는다."""
    configure_logging()
    _materialize_runtime_loggers()

    _run_alembic_env()

    assert logging.getLogger().level == logging.INFO, (
        "인프로세스 마이그레이션 후 root level 이 INFO 가 아님 "
        f"(현재: {logging.getLevelName(logging.getLogger().level)}) — alembic.ini "
        "[logger_root] level=WARN 이 앱 로깅을 덮어썼다. env.py 의 fileConfig 가드 회귀."
    )


def test_app_handler_survives_in_process_migration():
    """🔴 우리 stdout 핸들러(_MARKER)가 root 에 그대로 남는다 — alembic stderr 핸들러로 교체 금지."""
    configure_logging()
    _materialize_runtime_loggers()

    _run_alembic_env()

    root = logging.getLogger()
    assert any(getattr(h, _MARKER, False) for h in root.handlers), (
        "인프로세스 마이그레이션 후 앱 핸들러(_MARKER)가 root 에서 사라짐 "
        f"(현재 핸들러: {root.handlers}) — fileConfig 의 _clearExistingHandlers 가 제거했다. "
        "앱 INFO 로그가 다시 전부 소실된다."
    )


def test_app_logger_still_emits_info_after_in_process_migration():
    """🔴 `src.scheduler` 가 INFO 를 계속 통과시킨다 — 인앱 스케줄러(#1099) 배포 검증의 전제."""
    configure_logging()
    _materialize_runtime_loggers()

    _run_alembic_env()

    assert logging.getLogger(_APP_LOGGER).isEnabledFor(logging.INFO), (
        f"마이그레이션 후 {_APP_LOGGER} 가 INFO 를 못 통과시킴 — "
        "'scheduler started — N jobs' 가 운영 로그에 다시 안 보이게 된다."
    )


def test_uvicorn_access_logger_not_disabled_by_migration():
    """🔴 `uvicorn.access` 가 disabled 되지 않는다 — access 로그 24h 0건 사고의 직접 원인."""
    configure_logging()
    _materialize_runtime_loggers()

    _run_alembic_env()

    assert not logging.getLogger(_ACCESS_LOGGER).disabled, (
        f"마이그레이션 후 {_ACCESS_LOGGER} 가 disabled — fileConfig 의 "
        "disable_existing_loggers=True 가 적용됐다. uvicorn access 로그가 전부 사라진다."
    )


# --------------------------------------------------------------------------------------
# 가드 기전 (호출 여부) / guard mechanism — was fileConfig actually called?
# --------------------------------------------------------------------------------------

def test_file_config_skipped_when_app_already_configured(monkeypatch):
    """🔴 앱 로깅이 설정된 상태에서는 env.py 가 fileConfig 를 **호출하지 않는다**."""
    calls = []
    monkeypatch.setattr(
        "logging.config.fileConfig", lambda *a, **kw: calls.append((a, kw))
    )
    configure_logging()

    _run_alembic_env()

    assert not calls, (
        "앱이 이미 로깅을 설정했는데 env.py 가 fileConfig 를 호출 — "
        f"가드 미적용(호출 인자: {calls}). 인프로세스 마이그레이션이 앱 로깅을 파괴한다."
    )


def test_file_config_still_called_for_standalone_cli(monkeypatch):
    """🔴 CLI 경로 보존 — 앱이 로깅 미설정이면 env.py 가 기존대로 fileConfig 를 호출한다.

    가드가 `if False` 처럼 과잉 차단되면 `make migrate` 의 alembic 로그가 사라진다.
    Over-broad guarding would silence `make migrate` output, so assert the CLI path still configures.
    """
    calls = []
    monkeypatch.setattr(
        "logging.config.fileConfig", lambda *a, **kw: calls.append((a, kw))
    )
    _strip_app_logging()

    _run_alembic_env()

    assert len(calls) == 1, (
        f"alembic CLI 단독 경로에서 fileConfig 호출 횟수가 1 이 아님 ({len(calls)}) — "
        "가드가 과잉 차단해 `make migrate` 로그가 사라진다."
    )
    assert calls[0][0][0] == str(_ALEMBIC_INI), (
        f"fileConfig 가 alembic.ini 가 아닌 경로로 호출됨: {calls[0][0][0]!r}"
    )


# --------------------------------------------------------------------------------------
# 가드의 가드 / guard of the guard — keeps the tests above non-vacuous
# --------------------------------------------------------------------------------------

def test_raw_file_config_would_wipe_app_logging_premise():
    """🔴 전제 고정 — 가드 없이 alembic.ini 를 그대로 적용하면 앱 로깅이 실제로 파괴된다.

    위 회귀 가드들은 "alembic.ini 가 파괴적"이라는 전제 위에 서 있다. 누가 alembic.ini 의
    `[logger_root] level` 을 INFO 로 바꾸거나 `disable_existing_loggers` 를 끄면 위 단언들이
    **가드가 없어도 통과**하는 공허한 테스트로 변한다. 이 테스트가 그 순간 FAIL 해서 알린다
    (env.py 를 거치지 않고 fileConfig 를 직접 호출하므로 가드 구현과 무관하게 항상 성립).
    The guards above assume alembic.ini is destructive. If someone relaxes the ini, they would pass
    vacuously; this premise test fails at that moment. It bypasses env.py entirely, so it holds both
    before and after the guard is implemented.
    """
    configure_logging()
    _materialize_runtime_loggers()

    logging.config.fileConfig(str(_ALEMBIC_INI))

    root = logging.getLogger()
    assert root.level == logging.WARNING, (
        "alembic.ini 가 더 이상 root level 을 WARN 으로 낮추지 않는다 — "
        "이 파일의 회귀 가드들이 공허해졌다. 가드 유효성을 재설계할 것."
    )
    assert not any(getattr(h, _MARKER, False) for h in root.handlers), (
        "alembic.ini 적용 후에도 앱 핸들러가 남아있다 — 회귀 가드가 공허해졌다."
    )
    assert logging.getLogger(_ACCESS_LOGGER).disabled, (
        "alembic.ini 가 더 이상 기존 로거를 disable 하지 않는다 "
        "(disable_existing_loggers 비활성?) — 회귀 가드가 공허해졌다."
    )
