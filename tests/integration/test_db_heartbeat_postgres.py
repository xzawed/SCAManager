"""DB 쓰기 하트비트 — 실 PostgreSQL 에서 2026-10-25 꼴(연결 하나짜리 풀에 남은 세션 READ ONLY)을 만들고 되돌린다.
DB write heartbeat on real PostgreSQL: reproduce the 2026-10-25 shape (a session READ ONLY stuck on a
one-connection pool) and undo it; never touch a role-level READ ONLY; probe works under RLS FORCE.

CI `pg-concurrency` job 이 `DATABASE_URL_TEST_POSTGRES` 로 돌린다(ci.yml 에 파일 등재).
"""
# pylint: disable=redefined-outer-name
import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

from src.services import db_heartbeat_service as hb

_PG_URL = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
pytestmark = pytest.mark.skipif(
    not _PG_URL, reason="풀 연결 오염 · 회복은 실 PostgreSQL 로만 잰다 — DATABASE_URL_TEST_POSTGRES / needs PostgreSQL")

_ROLE, _PW = "heartbeat_app_ci", "heartbeat-ci-only"
_READ_ONLY_DEFAULT = "SELECT setting, source FROM pg_settings WHERE name = 'default_transaction_read_only'"


@pytest.fixture(scope="module")
def admin():
    """스키마를 비우고 head 까지 올린다 → 슈퍼유저 엔진 / reset the schema, upgrade to head, superuser engine."""
    from alembic import command
    from alembic.config import Config

    from src.config import settings as app_settings

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _PG_URL)
    with patch.object(app_settings, "database_url", _PG_URL):
        reset = create_engine(_PG_URL)
        with reset.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        reset.dispose()
        command.upgrade(cfg, "head")
    eng = create_engine(_PG_URL, isolation_level="AUTOCOMMIT")
    yield eng
    eng.dispose()


@pytest.fixture
def app_role(admin):
    """앱 웹 역할과 같은 모양 — NOBYPASSRLS · 비-owner · repositories 에 SELECT · UPDATE (RLS FORCE 대상).
    Shaped like the web app role: NOBYPASSRLS, non-owner, SELECT/UPDATE on repositories (RLS FORCE applies)."""
    with admin.connect() as conn:
        conn.execute(text(f"CREATE ROLE {_ROLE} LOGIN PASSWORD '{_PW}' NOBYPASSRLS"))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {_ROLE}"))
        conn.execute(text(f"GRANT SELECT, UPDATE ON repositories TO {_ROLE}"))
    url = make_url(_PG_URL).set(username=_ROLE, password=_PW)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"REVOKE ALL ON repositories FROM {_ROLE}"))
            conn.execute(text(f"REVOKE ALL ON SCHEMA public FROM {_ROLE}"))
            conn.execute(text(f"DROP ROLE IF EXISTS {_ROLE}"))


def _one_connection_pool(url):
    """사고 때 워커 풀처럼 서버 연결이 하나뿐인 풀 / a pool with a single server connection, like the incident."""
    eng = create_engine(url, pool_size=1, max_overflow=0)
    return eng, sessionmaker(bind=eng)


def test_session_read_only_on_the_only_connection_is_healed(app_role):
    """세션 READ ONLY 를 남기면 앱 쓰기가 25006 으로 막히고(대조군), 하트비트 한 번에 그 연결이 회복된다.
    A stuck session READ ONLY blocks writes (control); one heartbeat heals that very connection."""
    eng, factory = _one_connection_pool(app_role)
    try:
        with eng.connect() as conn:  # 오염 — 2026-10-25 와 같은 문장 / poison with the incident's statement
            conn = conn.execution_options(isolation_level="AUTOCOMMIT")
            conn.exec_driver_sql("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
            poisoned_pid = conn.exec_driver_sql("SELECT pg_backend_pid()").scalar()
        with factory() as session:  # 대조군 — 정말 막혔다 / control: writes really are blocked
            assert session.execute(text(_READ_ONLY_DEFAULT)).one() == ("on", "session")
            with pytest.raises(DBAPIError) as caught:
                session.execute(text("UPDATE repositories SET id = id WHERE false"))
            assert caught.value.orig.pgcode == "25006"

        assert hb.probe(factory) == ("healed", None)
        assert hb.probe(factory) == ("ok", None)
        with eng.connect() as conn:
            assert conn.exec_driver_sql("SELECT pg_backend_pid()").scalar() == poisoned_pid, "다른 연결을 쟀다"
            assert conn.exec_driver_sql("SHOW default_transaction_read_only").scalar() == "off"
    finally:
        eng.dispose()


def test_role_level_read_only_is_never_reset(admin, app_role):
    """역할 단위 READ ONLY(출처 user)는 되돌리지 않는다 — 쓰기가 막혔다고만 보고한다(대조군: 풀면 ok).
    A role-level READ ONLY (source `user`) is never reset; the probe only reports the block."""
    with admin.connect() as conn:
        conn.execute(text(f"ALTER ROLE {_ROLE} SET default_transaction_read_only = on"))
    eng, factory = _one_connection_pool(app_role)
    try:
        assert hb.probe(factory) == ("failed", "read-only:user")
        with factory() as session:
            assert session.execute(text(_READ_ONLY_DEFAULT)).one() == ("on", "user"), "하트비트가 손댔다"
    finally:
        eng.dispose()
        with admin.connect() as conn:
            conn.execute(text(f"ALTER ROLE {_ROLE} RESET default_transaction_read_only"))
    eng, factory = _one_connection_pool(app_role)
    try:
        assert hb.probe(factory) == ("ok", None)
    finally:
        eng.dispose()


def test_probe_takes_no_lock_on_application_tables(app_role):
    """하트비트 문장은 앱 테이블에 잠금을 하나도 잡지 않는다 — 클라이언트가 그 사이 멈춰도 마이그레이션을 세우지 않는다
    (Grok 반례 38408243: `UPDATE … WHERE false` 는 RowExclusiveLock 을 ROLLBACK 까지 쥐었다). 대조군으로 그 UPDATE 는 잡는다.
    The probe takes no lock on any application table; the old no-row UPDATE (control) does."""
    locks = text("SELECT count(*) FROM pg_locks l JOIN pg_class c ON c.oid = l.relation "
                 "JOIN pg_namespace n ON n.oid = c.relnamespace "
                 "WHERE l.pid = pg_backend_pid() AND n.nspname = 'public'")
    eng, factory = _one_connection_pool(app_role)
    try:
        with factory() as session:
            assert session.execute(hb.PROBE).one()[0] == "off"
            assert session.execute(locks).scalar() == 0
        with factory() as session:  # 대조군 / control
            session.execute(text("UPDATE repositories SET id = id WHERE false"))
            assert session.execute(locks).scalar() >= 1, "계기가 잠금을 못 본다 / the instrument cannot see locks"
        assert hb.probe(factory) == ("ok", None)
    finally:
        eng.dispose()
