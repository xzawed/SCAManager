from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# 앱 로깅 설정 여부 판별 — 아래 fileConfig 가드에서 사용 (인프로세스 마이그레이션 식별).
# Detects whether the app already configured logging; used by the fileConfig guard below.
from src.logging_config import is_configured

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# alembic config 의 DB URL 키 (중복 리터럴 제거 — SonarCloud S1192)
# Alembic config key for the DB URL (single literal — SonarCloud S1192)
_SQLALCHEMY_URL = "sqlalchemy.url"

# Interpret the config file for Python logging.
# This line sets up loggers basically.
# 🔴 앱이 이미 로깅을 설정했으면 건너뛴다 (2026-07-19 P0 — 인프로세스 마이그레이션이 앱 로깅을 파괴).
# `src/main.py` lifespan 은 configure_logging() 직후 `command.upgrade()` 로 이 파일을 실행한다.
# 그때 fileConfig 를 그대로 부르면 alembic.ini 의 `[logger_root] level = WARN` + stderr 핸들러가
# 우리 stdout 핸들러를 교체하고, 기본값 `disable_existing_loggers=True` 가 `uvicorn.access` 와
# 모든 `src.*` 로거를 비활성화한다 → 앱 INFO 로그·access 로그가 출시 이래 전부 소실됐다(#1100 무력화).
# alembic CLI 단독 실행(`make migrate`) 은 앱 설정이 없으므로 기존대로 ini 로깅을 적용한다.
# 🔴 Skip when the app already configured logging (2026-07-19 P0). The FastAPI lifespan runs
# migrations in-process right after configure_logging(); applying alembic.ini there would reset the
# root logger to WARN/stderr and disable uvicorn.access plus every src.* logger (the default
# disable_existing_loggers=True), silently dropping all application logs. Standalone CLI runs still
# get the ini logging config because the app marker is absent.
# 회귀 가드 / Regression guard: tests/unit/migrations/test_alembic_env_logging_guard.py
if config.config_file_name is not None and not is_configured():
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# 🔴 전 ORM 모델(13종) 명시 import 의무 — 일부만 import 하면 autogenerate 가 미등록 테이블을
# "삭제됨"으로 보고 drop_table 을 생성하는 데이터 손실 함정 (감사 migration-integrity-001, 2026-06-25).
# empty __init__.py 규칙(testing.md) 보존 — aggregate import 대신 여기서 전수 명시.
# 회귀 가드: tests/unit/migrations/test_alembic_env_model_completeness.py (신규 모델 추가 시 자동 fail).
# 🔴 Import EVERY ORM model (13) — a partial import makes autogenerate emit destructive drop_table for
# the unimported tables. The empty-__init__ convention is preserved; all models are listed here explicitly.
from src.models.repository import Repository  # noqa: F401
from src.models.analysis import Analysis      # noqa: F401
from src.models.analysis_attempt import AnalysisAttempt  # noqa: F401
from src.models.analysis_feedback import AnalysisFeedback  # noqa: F401
from src.models.repo_config import RepoConfig  # noqa: F401
from src.models.gate_decision import GateDecision  # noqa: F401
from src.models.merge_attempt import MergeAttempt  # noqa: F401
from src.models.merge_retry import MergeRetryQueue  # noqa: F401
from src.models.issue_registration import IssueRegistration  # noqa: F401
from src.models.insight_narrative_cache import InsightNarrativeCache  # noqa: F401
from src.models.security_alert_log import SecurityAlertProcessLog  # noqa: F401
from src.models.user import User  # noqa: F401
from src.models.claude_api_call import ClaudeApiCall  # noqa: F401
from src.database import Base, _build_connect_args
from src.config import settings

target_metadata = Base.metadata

# 🔴 전 ORM 모델(13) 실참조 — CodeQL py/unused-import(#528~536) 봉인.
# 각 import 의 `# noqa: F401` 은 flake8 만 억제하고 CodeQL py/unused-import 는 별도 룰이라
# 명시 참조로만 'used' 처리된다 (test_migration_completeness.py 의 _REGISTERED_MODELS 동일 패턴, #507~515).
# 이어지는 단언이 튜플을 실제로 읽어 py/unused-global-variable(상수 고아화, #515 류)도 함께 회피하며,
# import 부작용이 사라진 비정상 상태를 런타임에서 loud-fail 로 잡아 autogenerate drop_table 함정을 잠근다.
# 🔴 Reference every ORM model (13) so CodeQL py/unused-import (#528-536) is sealed; the per-import
# `# noqa: F401` silences flake8 only. The following assertion reads the tuple (avoiding an
# unused-global alert too) and loud-fails if the import side-effect ever breaks — locking the
# autogenerate drop_table footgun. Same pattern as test_migration_completeness.py.
_REGISTERED_MODELS = (
    Repository, Analysis, AnalysisAttempt, AnalysisFeedback, RepoConfig, GateDecision,
    MergeAttempt, MergeRetryQueue, IssueRegistration,
    InsightNarrativeCache, SecurityAlertProcessLog, User, ClaudeApiCall,
)
_unregistered_models = [
    m.__name__ for m in _REGISTERED_MODELS if m.__tablename__ not in target_metadata.tables
]
if _unregistered_models:  # pragma: no cover — import 부작용 소실 시에만 도달 / only if side-effect breaks
    raise RuntimeError(
        f"ORM 모델 테이블이 Base.metadata 에 미등록 — autogenerate drop_table 위험: {_unregistered_models}"
    )

# Override sqlalchemy.url from application settings.
# effective_migration_url = MIGRATION_DATABASE_URL or DATABASE_URL — RLS Phase 4 마이그레이션
# credential 게이트(owner role 분리). 미설정 시 DATABASE_URL 그대로 사용(현행 동작 보존).
# effective_migration_url = MIGRATION_DATABASE_URL or DATABASE_URL — RLS Phase 4 migration
# credential gate (owner role separation). Unset reuses DATABASE_URL (current behavior).
config.set_main_option(_SQLALCHEMY_URL, settings.effective_migration_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option(_SQLALCHEMY_URL)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = config.get_main_option(_SQLALCHEMY_URL, "")
    # db_force_ipv4/db_sslmode 설정을 동일하게 적용, connect_timeout=10으로 hang 방지
    # Apply db_force_ipv4/db_sslmode settings identically; connect_timeout=10 prevents hangs
    if url.startswith("postgresql"):
        connect_args = _build_connect_args(url)
        connect_args["connect_timeout"] = 10
    else:
        connect_args = {}
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
