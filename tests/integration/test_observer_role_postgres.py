"""관측 역할(0049) — 실 PostgreSQL 에서 읽을 수 있는 컬럼이 허용 목록과 정확히 같고, 쓰기 · 행 잠금 · 뺀 컬럼은
권한이 막는지 잰다.
Observer role (0049) on real PostgreSQL: readable columns equal the allowlist exactly, and writes, row locks
and excluded columns are refused by privileges.

SQLite 에는 역할이 없어 못 잰다 — CI `pg-concurrency` job 이 `DATABASE_URL_TEST_POSTGRES` 로 돌린다(ci.yml 에 파일 등재).
막히는 쪽은 `SET LOCAL ROLE` 로 잰다 — 역할 기본값(읽기 전용)이 걸리지 않는 더 센 경우라, 막혔다면 권한이 막은 것이다.
Refusals are measured through SET LOCAL ROLE, where the role's read-only default does not apply — the stronger case.
"""
# pylint: disable=redefined-outer-name
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

_PG_URL = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
pytestmark = pytest.mark.skipif(
    not _PG_URL, reason="관측 역할 권한은 실 PostgreSQL 로만 잰다 — DATABASE_URL_TEST_POSTGRES / needs PostgreSQL")

_MIGRATION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0049_observer_role.py"
_INSUFFICIENT_PRIVILEGE = "42501"


def _load_migration():
    spec = importlib.util.spec_from_file_location("observer_role_0049", _MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIG = _load_migration()
_ROLE = _MIG.ROLE


@pytest.fixture(scope="module")
def engine():
    """스키마를 비우고 head 까지 올린 뒤, 슈퍼유저로 사용자 1 · 리포 1 을 심는다.
    Reset the schema, upgrade to head, then seed one user and one repository as the superuser."""
    from alembic import command
    from alembic.config import Config

    from src.config import settings as app_settings

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _PG_URL)
    # env.py 가 cfg URL 을 settings.database_url 로 덮는다 — 싱글톤을 바꿔야 PG 로 돈다(db.md)
    # env.py overrides the cfg URL with settings.database_url — patch the singleton (db.md)
    with patch.object(app_settings, "database_url", _PG_URL):
        reset = create_engine(_PG_URL)
        with reset.begin() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        reset.dispose()
        command.upgrade(cfg, "head")
    eng = create_engine(_PG_URL)
    with eng.begin() as conn:
        conn.execute(text(
            "INSERT INTO users (github_id, github_login, email, display_name) "
            "VALUES ('9001', 'octo', 'octo@example.com', 'Octo')"))
        conn.execute(text(
            "INSERT INTO repositories (full_name, user_id, webhook_secret) "
            "SELECT 'octo/repo', id, 'whsec-test' FROM users WHERE github_id = '9001'"))
        conn.execute(text("ANALYZE users"))
    yield eng
    eng.dispose()


def _as_observer(conn, sql):
    conn.execute(text(f"SET LOCAL ROLE {_ROLE}"))
    return conn.execute(text(sql))


# --- 1. 권한 = 허용 목록 ----------------------------------------------------------


def test_readable_columns_are_exactly_the_allowlist(engine):
    """읽을 수 있는 컬럼(PUBLIC 경유 포함, 실효 권한) = `_ALLOWED`. 테이블 단위 SELECT 는 없다.
    Effective readable columns (including via PUBLIC) equal `_ALLOWED`; no table-level SELECT."""
    expected = {(table, column) for table, columns in _MIG._ALLOWED.items() for column in columns}
    with engine.connect() as conn:
        readable = set(conn.execute(text(
            "SELECT c.relname, a.attname FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f') "
            "AND has_column_privilege(:role, c.oid, a.attnum, 'SELECT')"), {"role": _ROLE}).all())
        table_wide = conn.execute(text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm', 'f') "
            "AND has_table_privilege(:role, c.oid, 'SELECT')"), {"role": _ROLE}).scalars().all()
    assert readable, "읽을 수 있는 컬럼이 0 이다 — 권한이 안 걸렸다 / no readable column at all"
    assert readable == expected, (
        f"허용 목록 밖에서 읽힘: {sorted(readable - expected)} · 허용인데 안 읽힘: {sorted(expected - readable)}")
    assert table_wide == [], f"테이블 단위 SELECT 가 있다(새 컬럼까지 보인다): {table_wide}"


def test_no_write_privilege_anywhere(engine):
    """어느 스키마의 어느 관계에도 쓰기 · 참조 · 트리거 권한이 없다(컬럼 단위 포함).
    No write, reference or trigger privilege on any relation in any schema, column-level included."""
    with engine.connect() as conn:
        found = conn.execute(text(
            "SELECT n.nspname, c.relname, p.priv FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "CROSS JOIN unnest(ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']) AS p(priv) "
            "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') "
            "AND c.relkind IN ('r', 'p', 'v', 'm', 'f') "
            "AND (has_table_privilege(:role, c.oid, p.priv) "
            "     OR (p.priv IN ('INSERT', 'UPDATE', 'REFERENCES') "
            "         AND has_any_column_privilege(:role, c.oid, p.priv)))"), {"role": _ROLE}).all()
    assert found == [], f"쓰기 계열 권한: {found}"


def test_role_attributes_and_defaults(engine):
    """BYPASSRLS 만 켜고 나머지 특권은 없다 · 소속 역할 없음 · 연결 2 · 로그인은 운영자가 연다 · 기본값 4개.
    Only BYPASSRLS; no other privilege, no membership, 2 connections, NOLOGIN until the operator, four defaults."""
    with engine.connect() as conn:
        attrs = conn.execute(text(
            "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolcanlogin, rolbypassrls, rolconnlimit "
            "FROM pg_roles WHERE rolname = :role"), {"role": _ROLE}).one()
        memberships = conn.execute(text(
            "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member "
            "WHERE r.rolname = :role"), {"role": _ROLE}).scalar()
        config = set(conn.execute(text(
            "SELECT unnest(s.setconfig) FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole "
            "WHERE r.rolname = :role AND s.setdatabase = 0"), {"role": _ROLE}).scalars().all())
    assert tuple(attrs) == (False, False, False, False, False, True, 2)
    assert memberships == 0
    # CI 는 슈퍼유저라 temp_file_limit 도 걸린다 — 운영(Supabase postgres)에서는 거절될 수 있다
    # CI runs as a superuser, so temp_file_limit is set too; production may refuse it
    assert config == {"default_transaction_read_only=on", "statement_timeout=5s",
                      "idle_in_transaction_session_timeout=10s", "temp_file_limit=256MB"}


# --- 2. 세션 동작 — 읽기는 되고, 나머지는 권한이 막는다 ------------------------------


@pytest.mark.parametrize("sql,rows", [
    ("SELECT id, preferred_language FROM users", 1),
    # RLS FORCE · app.user_id 없음 — BYPASSRLS 라 사용자 소유 행이 보인다 / owned row visible via BYPASSRLS
    ("SELECT id, full_name, user_id FROM repositories", 1),
    ("SELECT version_num FROM alembic_version", 1),
])
def test_observer_reads_allowlisted_columns(engine, sql, rows):
    """대조군 — 관측 역할이 아무것도 못 해서 막히는 게 아님을 먼저 보인다 / control: allowed reads succeed."""
    with engine.connect() as conn:
        with conn.begin():
            assert len(_as_observer(conn, sql).all()) == rows


def test_row_visibility_comes_from_bypassrls(engine):
    """계기 뒤집기 — 같은 컬럼 권한에 BYPASSRLS 만 없는 역할은 사용자 소유 행을 못 본다(롤백으로 흔적 없음).
    Flip: the same grant without BYPASSRLS sees no user-owned row (rolled back, nothing left behind)."""
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            conn.execute(text("CREATE ROLE observer_probe_norls NOLOGIN"))
            conn.execute(text("GRANT USAGE ON SCHEMA public TO observer_probe_norls"))
            conn.execute(text("GRANT SELECT (id) ON repositories TO observer_probe_norls"))
            conn.execute(text("SET LOCAL ROLE observer_probe_norls"))
            assert conn.execute(text("SELECT count(*) FROM repositories")).scalar() == 0
            conn.execute(text(f"SET LOCAL ROLE {_ROLE}"))
            assert conn.execute(text("SELECT count(*) FROM repositories")).scalar() == 1
        finally:
            trans.rollback()


@pytest.mark.parametrize("sql", [
    # 뺀 컬럼 — 출력 · 조건 · 행 전체 참조 · 실행 계획 어느 쪽으로도 / excluded columns, by any reference
    "SELECT email FROM users",
    "SELECT count(*) FROM users WHERE email IS NOT NULL",
    "SELECT u FROM users u",
    "SELECT to_jsonb(u) FROM users u",
    "EXPLAIN SELECT email FROM users",
    "SELECT webhook_secret FROM repositories",
    # 쓰기 — 읽기 전용 기본값이 없는 세션에서도 / writes, with no read-only default in force
    "UPDATE users SET preferred_language = preferred_language WHERE false",
    "DELETE FROM users WHERE false",
    "INSERT INTO analysis_attempts (repo_id, commit_sha, event) VALUES (1, 'x', 'push')",
    "TRUNCATE users",
    # 행 잠금 · 표 잠금 / row and table locks
    "SELECT id FROM users FOR UPDATE",
    "SELECT id FROM users FOR NO KEY UPDATE",
    "SELECT id FROM users FOR SHARE",
    "SELECT id FROM users FOR KEY SHARE",
    "LOCK TABLE users IN ACCESS SHARE MODE",
    # 객체 만들기 / creating objects
    "CREATE TABLE public.observer_probe (i int)",
    "CREATE VIEW public.observer_probe_v AS SELECT id FROM users",
])
def test_observer_is_refused_by_privilege(engine, sql):
    """권한 거부(42501)로 막힌다 — 다른 오류로 막힌 것은 통과로 치지 않는다.
    Refused with insufficient_privilege (42501); any other error does not count."""
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            with pytest.raises(DBAPIError) as caught:
                _as_observer(conn, sql)
            assert caught.value.orig.pgcode == _INSUFFICIENT_PRIVILEGE, caught.value.orig.pgerror
        finally:
            trans.rollback()


def test_pg_stats_hides_excluded_columns(engine):
    """통계 뷰는 컬럼 권한으로 걸러진다 — 뺀 컬럼의 대표값이 새지 않는다(대조군: 허용 컬럼은 보인다).
    pg_stats filters by column privilege: no sample values of excluded columns (control: allowed column shows)."""
    with engine.connect() as conn:
        with conn.begin():
            names = set(_as_observer(conn, "SELECT attname FROM pg_stats WHERE tablename = 'users'").scalars())
    assert "id" in names, f"대조군 실패 — 허용 컬럼 통계가 안 보인다: {names}"
    assert not names & {"email", "display_name", "github_login", "github_access_token"}, names


# --- 3. 로그인 세션 — 역할 기본값이 실제로 걸린다 ------------------------------------


def test_login_session_gets_the_role_defaults(engine):
    """운영자가 로그인을 열면(여기서는 시험 비밀번호) 그 세션은 읽기 전용 · 5초 제한으로 시작한다.
    Once login is enabled, a session starts read-only with the 5 s statement timeout."""
    with engine.begin() as conn:
        conn.execute(text(f"ALTER ROLE {_ROLE} LOGIN PASSWORD 'observer-ci-only'"))
    try:
        observer = create_engine(make_url(_PG_URL).set(username=_ROLE, password="observer-ci-only"))
        try:
            with observer.connect() as conn:
                assert conn.execute(text("SELECT current_user")).scalar() == _ROLE
                assert conn.execute(text("SHOW default_transaction_read_only")).scalar() == "on"
                assert conn.execute(text("SHOW statement_timeout")).scalar() == "5s"
                assert conn.execute(text("SELECT count(*) FROM repositories")).scalar() == 1
        finally:
            observer.dispose()
    finally:
        with engine.begin() as conn:
            conn.execute(text(f"ALTER ROLE {_ROLE} NOLOGIN PASSWORD NULL"))


def test_tool_bracket_cannot_be_escaped(engine):
    """조회 도구의 읽기 전용 괄호를 넘긴 SQL 로 깰 수 없다(Grok 반례 99a33064 — `COMMIT; …` 가 괄호를 닫았다).
    COMMIT · SET · 괄호 닫기 꼴은 서버가 거부하고, set_config 로 바꾼 세션 값은 ROLLBACK 이 되돌린다.
    The tool's read-only bracket cannot be broken by the SQL it is given (Grok counterexample: `COMMIT; …`)."""
    import psycopg2

    from scripts import observe_db

    with engine.begin() as conn:
        conn.execute(text(f"ALTER ROLE {_ROLE} LOGIN PASSWORD 'observer-ci-only'"))
    url = make_url(_PG_URL)
    raw = psycopg2.connect(host=url.host, port=url.port or 5432, dbname=url.database, user=_ROLE,
                           password="observer-ci-only")
    try:
        raw.autocommit = True
        columns, rows = observe_db.read_only(raw, "SELECT id, full_name FROM repositories;", 50)
        assert columns == ["id", "full_name"] and len(rows) == 1, (columns, rows)
        for escape in ("COMMIT; SET SESSION statement_timeout = 0",
                       "SET statement_timeout = 0",
                       "SELECT 1) q; COMMIT; SELECT * FROM (SELECT 1",
                       "SELECT id FROM users FOR UPDATE"):
            with pytest.raises(psycopg2.Error):
                observe_db.read_only(raw, escape, 50)
        observe_db.read_only(raw, "SELECT set_config('statement_timeout', '0', false)", 50)
        cur = raw.cursor()
        cur.execute("SHOW statement_timeout")
        assert cur.fetchone()[0] == "5s", "괄호 안 세션 값 변경이 남았다 / a session change survived the bracket"
        assert raw.get_transaction_status() == psycopg2.extensions.TRANSACTION_STATUS_IDLE
    finally:
        raw.close()
        with engine.begin() as conn:
            conn.execute(text(f"ALTER ROLE {_ROLE} NOLOGIN PASSWORD NULL"))


def test_downgrade_tolerates_dependent_grants(engine):
    """누가 관측 역할에 grant 권한을 손으로 줘 남에게 다시 준 상태 — 기본(RESTRICT) REVOKE 가 2BP01 로 막혀도 downgrade
    는 멈추지 않고 아무것도 바꾸지 않는다(Grok 반례 9213858d). 마이그레이션 자신은 grant 권한을 주지 않는다.
    Someone gave the observer a grant option and it re-granted: RESTRICT REVOKE fails with 2BP01, yet the downgrade
    neither stops nor changes anything. The migration itself never grants a grant option."""
    from alembic import command
    from alembic.config import Config

    from src.config import settings as app_settings

    admin = create_engine(_PG_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text("CREATE ROLE observer_dependent_sim NOLOGIN"))
            conn.execute(text(f"GRANT SELECT (id) ON repositories TO {_ROLE} WITH GRANT OPTION"))
            conn.execute(text(f"SET ROLE {_ROLE}"))
            conn.execute(text("GRANT SELECT (id) ON repositories TO observer_dependent_sim"))
            conn.execute(text("RESET ROLE"))
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", _PG_URL)
        with patch.object(app_settings, "database_url", _PG_URL):
            command.downgrade(cfg, "0048")  # 예전에는 2BP01 로 멈췄다 / used to stop with 2BP01
        with admin.connect() as conn:
            kept = conn.execute(text("SELECT has_column_privilege(:r, 'repositories', 'id', 'SELECT')"),
                                {"r": _ROLE}).scalar()
        assert kept is True, "되돌릴 수 없는 상태에서 일부만 거뒀다 / partially revoked"
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"REVOKE ALL ON repositories FROM {_ROLE} CASCADE"))
            conn.execute(text("DROP ROLE IF EXISTS observer_dependent_sim"))
        admin.dispose()
        _restore_shared_role()


def test_downgrade_is_all_or_nothing_when_drop_role_is_blocked(engine):
    """이 revision 이 거두지 않는 객체(시퀀스)에 권한이 있어 DROP ROLE 이 막히면, 표 · 스키마 권한도 그대로 둔다 —
    반쪽 상태가 없다(Grok 반례 069811ea: 안쪽 처리기가 표 권한만 거두고 시퀀스 권한을 남겼다).
    When DROP ROLE is blocked by a privilege this revision does not revoke (a sequence), table and schema privileges
    stay too: no half state."""
    from alembic import command
    from alembic.config import Config

    from src.config import settings as app_settings

    admin = create_engine(_PG_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            seq = conn.execute(text("SELECT pg_get_serial_sequence('repositories', 'id')")).scalar()
            conn.execute(text(f"GRANT USAGE ON SEQUENCE {seq} TO {_ROLE}"))
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", _PG_URL)
        with patch.object(app_settings, "database_url", _PG_URL):
            command.downgrade(cfg, "0048")
        with admin.connect() as conn:
            state = conn.execute(text(
                "SELECT has_column_privilege(:r, 'repositories', 'id', 'SELECT'), "
                "has_schema_privilege(:r, 'public', 'USAGE'), has_sequence_privilege(:r, :s, 'USAGE')"),
                {"r": _ROLE, "s": seq}).one()
        assert tuple(state) == (True, True, True), f"반쪽 상태 / half state: {tuple(state)}"
    finally:
        with admin.connect() as conn:
            conn.execute(text(f"REVOKE ALL ON SEQUENCE {seq} FROM {_ROLE}"))
        admin.dispose()
        _restore_shared_role()


# --- 4. 운영과 같은 소유자 — 슈퍼유저가 아닌 CREATEROLE · BYPASSRLS ------------------------
# 이 파일의 마지막에 둔다 — 공유 역할을 지웠다가 되살린다 / keep last: drops and restores the shared role


def _role_state(conn):
    row = conn.execute(text(
        "SELECT r.rolbypassrls, r.rolcanlogin, r.rolconnlimit, "
        "(SELECT count(*) FROM information_schema.column_privileges WHERE grantee = r.rolname), "
        "(SELECT setconfig FROM pg_db_role_setting s WHERE s.setrole = r.oid AND s.setdatabase = 0) "
        "FROM pg_roles r WHERE r.rolname = :role"), {"role": _ROLE}).one_or_none()
    return None if row is None else (row[0], row[1], row[2], row[3], set(row[4] or ()))


def test_migration_runs_as_a_non_superuser_owner(engine):
    """운영(Supabase `postgres`)처럼 슈퍼유저가 아닌 소유자로 올리고 · 내리고 · 다시 올린다.
    CI 는 슈퍼유저라 이 경로를 못 본다 — `DROP OWNED BY` 가 여기서만 «permission denied» 로 막혔다.
    temp_file_limit 은 superuser 전용이라 이 경로에서는 경고만 남기고 빠진다.
    Upgrade, downgrade and upgrade again as a non-superuser owner (CREATEROLE + BYPASSRLS), like production.
    The superuser CI path cannot see this; DROP OWNED BY was refused only here. temp_file_limit is skipped."""
    from alembic import command
    from alembic.config import Config

    from src.config import settings as app_settings

    base = make_url(_PG_URL)
    sim_url = (f"postgresql+psycopg2://observer_owner_sim:sim-ci-only@{base.host}:{base.port or 5432}"
               "/observer_sim")
    admin = create_engine(_PG_URL, isolation_level="AUTOCOMMIT")
    expected_columns = sum(len(columns) for columns in _MIG._ALLOWED.values())
    defaults = {"default_transaction_read_only=on", "statement_timeout=5s", "idle_in_transaction_session_timeout=10s"}
    try:
        with admin.connect() as conn:
            conn.execute(text(f"DROP OWNED BY {_ROLE}"))
            conn.execute(text(f"DROP ROLE {_ROLE}"))
            conn.execute(text("CREATE ROLE observer_owner_sim LOGIN PASSWORD 'sim-ci-only' CREATEROLE BYPASSRLS"))
            conn.execute(text("CREATE DATABASE observer_sim OWNER observer_owner_sim"))
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", sim_url)
        sim = create_engine(sim_url)
        try:
            with patch.object(app_settings, "database_url", sim_url):
                command.upgrade(cfg, "head")
                with sim.connect() as conn:
                    assert _role_state(conn) == (True, False, 2, expected_columns, defaults)
                command.downgrade(cfg, "0048")
                with sim.connect() as conn:
                    assert _role_state(conn) is None, "내렸는데 역할이 남았다 / role survived the downgrade"
                command.upgrade(cfg, "head")
                with sim.connect() as conn:
                    assert _role_state(conn) == (True, False, 2, expected_columns, defaults)
        finally:
            sim.dispose()
    finally:
        with admin.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS observer_sim WITH (FORCE)"))
            conn.execute(text(f"DROP ROLE IF EXISTS {_ROLE}"))
            conn.execute(text("DROP ROLE IF EXISTS observer_owner_sim"))
        admin.dispose()
        _restore_shared_role()


def _restore_shared_role():
    """공유 DB 의 역할을 되살린다 — 뒤에 도는 시험이 head 상태를 기대한다 / restore the role in the shared DB."""
    from alembic import command
    from alembic.config import Config

    from src.config import settings as app_settings

    restore_cfg = Config("alembic.ini")
    restore_cfg.set_main_option("sqlalchemy.url", _PG_URL)
    with patch.object(app_settings, "database_url", _PG_URL):
        command.downgrade(restore_cfg, "0048")
        command.upgrade(restore_cfg, "head")


def test_downgrade_tolerates_a_role_it_did_not_create(engine):
    """미리 있던 역할(슈퍼유저가 만들고 스키마 USAGE 를 준) — grant 권한 없는 소유자가 올리고 내려도 마이그레이션이
    멈추지 않는다. 이 revision 이 만들지 않은 역할은 경고만 남기고 그대로 둔다(Grok 반례 56c18d96 — 예전 downgrade 는
    DROP ROLE · REVOKE 의 42501 로 중단됐다).
    A pre-existing role (created by a superuser, schema USAGE from the schema owner): upgrading and downgrading as an
    owner without grant options never stops the migration; the role it did not create is left in place with a warning."""
    from alembic import command
    from alembic.config import Config

    from src.config import settings as app_settings

    base = make_url(_PG_URL)
    runner_url = (f"postgresql+psycopg2://observer_runner_sim:runner-ci-only@{base.host}:{base.port or 5432}"
                  "/observer_sim2")
    admin = create_engine(_PG_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f"DROP OWNED BY {_ROLE}"))
            conn.execute(text(f"DROP ROLE {_ROLE}"))
            conn.execute(text("CREATE ROLE observer_runner_sim LOGIN PASSWORD 'runner-ci-only' CREATEROLE BYPASSRLS"))
            conn.execute(text("CREATE DATABASE observer_sim2"))  # 슈퍼유저 소유 / owned by the superuser
            conn.execute(text(f"CREATE ROLE {_ROLE} NOLOGIN"))  # 이 revision 이 만들지 않은 역할 / not ours
        sim_admin = create_engine(make_url(_PG_URL).set(database="observer_sim2"), isolation_level="AUTOCOMMIT")
        try:
            with sim_admin.connect() as conn:
                conn.execute(text("GRANT CREATE, USAGE ON SCHEMA public TO observer_runner_sim"))  # grant 권한 없음
                conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {_ROLE}"))  # 스키마 소유자 쪽이 준 권한
        finally:
            sim_admin.dispose()
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", runner_url)
        with patch.object(app_settings, "database_url", runner_url):
            command.upgrade(cfg, "head")
            command.downgrade(cfg, "0048")  # 예전에는 여기서 42501 로 멈췄다 / used to stop here with 42501
        with admin.connect() as conn:
            kept = conn.execute(text("SELECT count(*) FROM pg_roles WHERE rolname = :r"), {"r": _ROLE}).scalar()
        assert kept == 1, "만들지 않은 역할을 지웠다 / dropped a role this revision did not create"
    finally:
        with admin.connect() as conn:
            conn.execute(text("DROP DATABASE IF EXISTS observer_sim2 WITH (FORCE)"))
            conn.execute(text(f"DROP ROLE IF EXISTS {_ROLE}"))
            conn.execute(text("DROP ROLE IF EXISTS observer_runner_sim"))
        admin.dispose()
        _restore_shared_role()
