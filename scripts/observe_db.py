"""운영 DB 읽기 — 관측 역할(`scamanager_observer`)로만, 한 번에 하나, 읽기 전용 트랜잭션 안에서 (회고 원장 L02).
Read production rows as the observer role only: one run at a time, inside a read-only transaction.

    py -3 scripts/observe_db.py "SELECT id, status, last_failure_reason FROM merge_retry_queue ORDER BY id DESC LIMIT 5"
    py -3 scripts/observe_db.py --max-rows 200 "SELECT ..."
    py -3 scripts/observe_db.py --audit        # 이 역할이 읽을 수 있는 것 · 할 수 있는 것 / what this role can read and do

- 주소는 `OBSERVER_DATABASE_URL`(환경변수, 없으면 리포 `.env` 의 그 줄 하나만)에서 읽고 출력하지 않는다.
  관측 역할이 아닌 주소면 연결하지 않고, 연결 뒤에도 `current_user` 로 한 번 더 확인한다.
- 읽을 수 있는 컬럼은 `alembic/versions/0049_observer_role.py::_ALLOWED` 가 정한다. 그 밖은 «권한 거부» 다.
- SQL 은 서버의 `query_to_xml`(SPI 읽기 전용) 안에서 돈다 — SELECT · VALUES · WITH 만 되고, COMMIT · SET ·
  PREPARE · FOR UPDATE 는 서버가 거부한다. EXPLAIN · SHOW 는 안 된다(설정은 `pg_settings` 를 SELECT 한다).
- 셀마다 `src.logging_config._redact`(봇 URL · 웹훅 경로 · 토큰 쿼리 · URL 비밀번호)를 거쳐 300자로 자르고,
  기본 50행(최대 500)만 찍는다.
- 한 번에 하나만 돈다(127.0.0.1 포트 잠금) — 여럿이 떠서 앱과 함께 쓰는 Supavisor 연결 한도를 채우지 않게.
- 비밀번호 설정 · 교체는 `scripts/observer_setup.py`(사용자가 실행).

exit 0 = 됐다 · 1 = 거부(다른 조회가 도는 중 · 관측 역할 아님) · 2 = 조회 오류 · 3 = 설정 · 연결 실패
exit 0 ok · 1 refused · 2 query error · 3 setup or connection failure
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from defusedxml import ElementTree  # noqa: E402  # pylint: disable=wrong-import-position

from src.logging_config import _redact  # noqa: E402  # pylint: disable=wrong-import-position

ROLE = "scamanager_observer"
# 넘긴 SQL 은 %s 리터럴로만 들어간다 — 서버가 이어 붙여 SPI 읽기 전용으로 실행한다
# The caller's SQL is bound as a literal; the server concatenates it and runs it through read-only SPI.
_WRAPPED_QUERY = ("SELECT query_to_xml('SELECT * FROM (' || %s || E'\\n) AS observer_q LIMIT ' || %s, "
                  "true, false, '')")
_XSI_NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
_XML_NAME_ESCAPE = re.compile(r"_x([0-9A-Fa-f]{8}|[0-9A-Fa-f]{4})_")
ENV_KEY = "OBSERVER_DATABASE_URL"
LOCK_PORT = 47613  # 한 번에 하나 — 이 PC 의 다른 실행이 쥐고 있으면 거부 / single-instance lock
DEFAULT_ROWS, MAX_ROWS, CELL_LIMIT = 50, 500, 300
STATEMENT_TIMEOUT = "5s"
_INSUFFICIENT_PRIVILEGE = "42501"

# --audit — 읽기 전용 카탈로그 조회만 / catalog reads only
_AUDIT = (
    ("역할 속성 / role attributes",
     "SELECT current_user, rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls, rolconnlimit "
     "FROM pg_roles WHERE rolname = current_user"),
    ("소속 역할(비어야 한다) / memberships (must be empty)",
     "SELECT b.rolname FROM pg_auth_members m JOIN pg_roles b ON b.oid = m.roleid "
     "JOIN pg_roles u ON u.oid = m.member WHERE u.rolname = current_user"),
    ("읽을 수 있는 관계 / readable relations",
     "SELECT n.nspname, c.relname, c.relkind FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
     "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%' "
     "AND c.relkind IN ('r', 'p', 'v', 'm', 'f') AND has_any_column_privilege(c.oid, 'SELECT') ORDER BY 1, 2"),
    ("쓰기 계열 권한(비어야 한다) / write privileges (must be empty)",
     "SELECT n.nspname, c.relname, p.priv FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
     "CROSS JOIN unnest(ARRAY['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER']) AS p(priv) "
     "WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND c.relkind IN ('r', 'p', 'v', 'm', 'f') "
     "AND (has_table_privilege(c.oid, p.priv) "
     "OR (p.priv IN ('INSERT', 'UPDATE', 'REFERENCES') AND has_any_column_privilege(c.oid, p.priv))) ORDER BY 1, 2"),
    ("객체를 만들 수 있는 스키마(비어야 한다) / schemas with CREATE (must be empty)",
     "SELECT nspname FROM pg_namespace WHERE has_schema_privilege(oid, 'CREATE') ORDER BY 1"),
    ("실행할 수 있는 SECURITY DEFINER 함수 / executable SECURITY DEFINER functions",
     "SELECT n.nspname, p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
     "WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog', 'information_schema') "
     "AND has_function_privilege(p.oid, 'EXECUTE') ORDER BY 1, 2"),
    ("세션 설정 / session settings",
     "SELECT name, setting, unit FROM pg_settings WHERE name IN ('default_transaction_read_only', "
     "'statement_timeout', 'idle_in_transaction_session_timeout', 'temp_file_limit', 'server_version') ORDER BY 1"),
)


class Refused(Exception):
    """실행하지 않고 멈춘다(exit 1) / stop without running anything (exit 1)."""


def _env_key(line: str) -> str | None:
    stripped = line.lstrip("﻿").strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export "):]
    return stripped.split("=", 1)[0].strip()


def load_url(environ, env_file: Path) -> str | None:
    """환경변수가 먼저, 없으면 `.env` 의 `OBSERVER_DATABASE_URL` 줄 하나만 읽는다(다른 줄은 보지 않는다).
    The environment wins; otherwise only the OBSERVER_DATABASE_URL line of .env is read."""
    value = environ.get(ENV_KEY, "").strip()
    if value:
        return value
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        if _env_key(line) == ENV_KEY:
            value = line.split("=", 1)[1].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            return value or None
    return None


def url_role(url: str) -> str:
    """드라이버가 실제로 쓸 사용자의 역할 부분(Supavisor 꼴 `역할.ref` 의 앞) — 주소 글자가 아니라 libpq 가
    읽은 값이다. 쿼리의 `user=` 처럼 주소의 사용자를 덮는 꼴까지 반영한다. 못 읽거나 `service=` 로 바깥 설정을
    부르면 빈 값(= 거부).
    The role part of the user libpq will actually use (parsed by psycopg2, so `?user=` overrides count);
    unparsable input or an external `service=` yields empty, i.e. refusal."""
    from psycopg2 import ProgrammingError  # pylint: disable=import-outside-toplevel
    from psycopg2.extensions import parse_dsn  # pylint: disable=import-outside-toplevel
    try:
        params = parse_dsn(_connect_kwargs(url)[0])
    except ProgrammingError:
        return ""
    if "service" in params:
        return ""
    return params.get("user", "").split(".", 1)[0]


def acquire_lock(port: int = LOCK_PORT):
    """127.0.0.1 포트를 쥔다 — 이미 쥐어져 있으면 None. 프로세스가 끝나면 저절로 풀린다.
    Hold a localhost port; None if another run holds it. Released when the process exits."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # Windows — 다른 프로세스의 재사용 바인드를 막는다
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        sock.bind(("127.0.0.1", port))
    except OSError:
        sock.close()
        return None
    return sock


def _connect_kwargs(url: str) -> tuple[str, dict]:
    dsn = url.replace("postgresql+psycopg2://", "postgresql://", 1)
    kwargs = {"connect_timeout": 10, "application_name": "scamanager-observer"}
    if "sslmode" not in parse_qs(urlsplit(dsn).query):
        kwargs["sslmode"] = "require"
    return dsn, kwargs


def cell(value) -> str:
    """셀 하나 — 비밀 꼴을 가리고, 한 줄로 펴고, 자른다 / mask secret shapes, flatten, cut."""
    text = "NULL" if value is None else str(value)
    text = _redact(text).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    return text if len(text) <= CELL_LIMIT else text[:CELL_LIMIT] + "..."


def _print_rows(columns, rows, limit, out) -> None:
    print("\t".join(columns), file=out)
    for row in rows[:limit]:
        print("\t".join(cell(v) for v in row), file=out)
    if len(rows) > limit:
        print(f"(앞 {limit}행만 — 더 있다. 조건을 좁힌다 / first {limit} rows only)", file=out)
    else:
        print(f"({len(rows)}행 / rows)", file=out)


def _column_name(tag: str) -> str:
    """SQL/XML 이 이름에 넣은 `_xHHHH_` 를 되돌린다(예: `?column?`) / undo the SQL/XML name escaping."""
    return _XML_NAME_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), tag)


def parse_table_xml(xml_text: str):
    """`query_to_xml(…, nulls => true, tableforest => false)` 결과 → (컬럼, 행). 빈 결과는 컬럼도 없다.
    Turn query_to_xml output into (columns, rows); an empty result carries no column names."""
    root = ElementTree.fromstring(xml_text)
    columns, rows = [], []
    for row in root:
        cells = list(row)
        if not columns:
            columns = [_column_name(c.tag) for c in cells]
        rows.append(tuple(None if c.get(_XSI_NIL) == "true" else (c.text or "") for c in cells))
    return columns, rows


def read_only(conn, sql: str, limit: int):
    """`BEGIN READ ONLY` 안에서 서버의 `query_to_xml`(SPI 읽기 전용)로 실행하고, 무엇이 실패해도 ROLLBACK 을 보낸다.
    문장을 글자로 세지 않는다 — 넘긴 글자는 SQL 리터럴 하나라 괄호를 닫을 수 없고, 서버가 트랜잭션 제어(COMMIT) ·
    SET · PREPARE · FOR UPDATE 를 거부한다. `set_config` 같은 세션 값 변경은 ROLLBACK 이 되돌린다(로컬 PG 17 실측).
    바깥 SELECT 의 LIMIT 이 서버에서 행을 자른다 — 맨 끝 `;` 는 떼고, 줄 주석이 닫는 괄호를 먹지 않게 줄을 바꾼다.
    Runs through the server's read-only SPI (query_to_xml) inside BEGIN READ ONLY and always ends with ROLLBACK.
    The text travels as one literal, so it cannot close the bracket; the server refuses COMMIT, SET, PREPARE and
    FOR UPDATE there, and ROLLBACK reverts set_config. The outer LIMIT caps rows server-side."""
    cur = conn.cursor()
    try:
        cur.execute("BEGIN READ ONLY")
        cur.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
        cur.execute(_WRAPPED_QUERY, (sql.strip().rstrip(";").rstrip(), limit + 1))
        return parse_table_xml(cur.fetchone()[0])
    finally:
        try:
            cur.execute("ROLLBACK")
        except Exception:  # pylint: disable=broad-exception-caught
            # 연결이 이미 끊겼으면 서버가 트랜잭션을 버린다 — 원래 오류를 가리지 않게 삼킨다
            # A dropped connection discards the transaction server-side; keep the original error visible.
            pass


def main(argv: list[str] | None = None, *, environ=None, env_file: Path | None = None,
         connect=None, lock=acquire_lock, out=None) -> int:
    out = out or sys.stdout
    environ = os.environ if environ is None else environ
    env_file = env_file or ROOT / ".env"
    parser = argparse.ArgumentParser(description="관측 역할로 운영 DB 읽기 / read production as the observer role")
    parser.add_argument("sql", nargs="?", help="SELECT 한 문장 / one SELECT statement")
    parser.add_argument("--audit", action="store_true", help="이 역할이 읽고 할 수 있는 것 / what this role can do")
    parser.add_argument("--max-rows", type=int, default=DEFAULT_ROWS)
    args = parser.parse_args(argv)
    if bool(args.sql) == args.audit:
        parser.error("SQL 한 문장이나 --audit 중 하나만 / give one SQL statement or --audit")
    limit = max(1, min(args.max_rows, MAX_ROWS))

    url = load_url(environ, env_file)
    if not url:
        print(f"{ENV_KEY} 가 없다 — 사용자가 `py -3 scripts/observer_setup.py` 를 먼저 실행한다.", file=out)
        return 3
    if url_role(url) != ROLE:
        print(f"{ENV_KEY} 의 역할이 {ROLE} 가 아니다 — 다른 자격으로는 연결하지 않는다.", file=out)
        return 1
    held = lock()
    if held is None:
        print("다른 조회가 돌고 있다 — 끝난 뒤 다시 / another run holds the lock.", file=out)
        return 1
    try:
        return _run(args, url, limit, connect, out)
    finally:
        held.close()


def _run(args, url, limit, connect, out) -> int:
    if connect is None:
        import psycopg2  # pylint: disable=import-outside-toplevel
        connect = psycopg2.connect
    dsn, kwargs = _connect_kwargs(url)
    try:
        conn = connect(dsn, **kwargs)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"연결 실패 / connection failed: {_redact(str(exc)).strip()}", file=out)
        return 3
    try:
        conn.autocommit = True  # BEGIN 은 우리가 직접 보낸다 / we send BEGIN READ ONLY ourselves
        cur = conn.cursor()
        cur.execute("SELECT current_user")
        if cur.fetchone()[0] != ROLE:
            print(f"연결한 역할이 {ROLE} 가 아니다 — 조회하지 않는다.", file=out)
            return 1
        statements = _AUDIT if args.audit else (("", args.sql),)
        for title, sql in statements:
            if title:
                print(f"\n== {title}", file=out)
            try:
                columns, rows = read_only(conn, sql, limit if not args.audit else MAX_ROWS)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                print(f"조회 오류 / query error: {_redact(str(exc)).strip()}", file=out)
                if getattr(exc, "pgcode", None) == _INSUFFICIENT_PRIVILEGE:
                    print("관측 역할은 허용 컬럼만 읽는다 — 목록 = alembic/versions/0049_observer_role.py::_ALLOWED "
                          "(새 컬럼은 GRANT 하는 revision 이 있어야 보인다)", file=out)
                return 2
            _print_rows(columns, rows, limit if not args.audit else MAX_ROWS, out)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
