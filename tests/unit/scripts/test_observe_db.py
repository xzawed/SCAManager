"""운영 DB 조회 도구 — 관측 역할만 · 읽기 전용 트랜잭션 · 가림 · 행 상한 · 한 번에 하나 (회고 원장 L02).
The production read tool: observer role only, read-only transaction, masking, row cap, single instance.

가짜 연결로 «보내는 문장 순서» 와 «출력» 을 잰다. 실제 권한 경계는 tests/integration/test_observer_role_postgres.py 가 잰다.
A fake connection measures the statements sent and the output; the privilege boundary itself is measured on real PG.
"""
import io
from xml.sax.saxutils import escape

import pytest

from scripts import observe_db as od

_PW = "s3cretpassw0rd"
_URL = f"postgresql://scamanager_observer.abcref:{_PW}@aws-1-us-east-1.pooler.supabase.com:6543/postgres"


class _PgError(Exception):
    def __init__(self, message, pgcode=None):
        super().__init__(message)
        self.pgcode = pgcode


def _table_xml(columns, rows):
    """서버의 query_to_xml 출력 꼴(널 = xsi:nil) / the shape query_to_xml returns (nulls as xsi:nil)."""
    body = []
    for row in rows:
        cells = "".join(f'<{c} xsi:nil="true"/>' if v is None else f"<{c}>{escape(str(v))}</{c}>"
                        for c, v in zip(columns, row))
        body.append(f"<row>{cells}</row>")
    return f'<table xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">{"".join(body)}</table>'


class _Cursor:
    def __init__(self, conn):
        self.conn = conn
        self._rows = []

    def execute(self, sql, params=None):
        self.conn.sent.append(sql)
        self.conn.params.append(params)
        if sql == "SELECT current_user":
            self._rows = [(self.conn.user,)]
            return
        if sql in ("BEGIN READ ONLY", "ROLLBACK") or sql.startswith("SET LOCAL"):
            return
        assert sql == od._WRAPPED_QUERY, f"감싸지 않은 SQL 이 나갔다 / unwrapped SQL sent: {sql!r}"
        if self.conn.error is not None:
            raise self.conn.error
        limit = params[1]  # 서버의 바깥 LIMIT 처럼 자른다 / cut like the server-side outer LIMIT
        self._rows = [(_table_xml(self.conn.columns, list(self.conn.rows)[:limit]),)]

    def fetchone(self):
        return self._rows[0]


class _Conn:
    def __init__(self, user="scamanager_observer", columns=("id",), rows=((1,),), error=None):
        self.user, self.columns, self.rows, self.error = user, columns, rows, error
        self.sent, self.params, self.closed, self.autocommit = [], [], False, False

    def cursor(self):
        return _Cursor(self)

    def close(self):
        self.closed = True


class _Lock:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def _run(argv, conn=None, url=_URL, lock_free=True, connect_error=None, tmp_path=None):
    out = io.StringIO()
    calls = []

    def connect(dsn, **kwargs):
        calls.append((dsn, kwargs))
        if connect_error is not None:
            raise connect_error
        return conn

    lock = _Lock()
    environ = {od.ENV_KEY: url} if url else {}
    code = od.main(argv, environ=environ, env_file=(tmp_path / ".env") if tmp_path else None,
                   connect=connect, lock=(lambda: lock) if lock_free else (lambda: None), out=out)
    return code, out.getvalue(), calls, lock


# --- 1. 보내는 문장 ----------------------------------------------------------------


def test_query_runs_inside_read_only_transaction_and_always_rolls_back():
    """BEGIN READ ONLY → SET LOCAL 시간 제한 → 감싼 질의 → ROLLBACK. 넘긴 SQL 은 문장이 아니라 리터럴 값으로만 간다.
    BEGIN READ ONLY, SET LOCAL timeout, the wrapped query, ROLLBACK; the caller's SQL travels only as a bound value."""
    conn = _Conn()
    code, _out, calls, lock = _run(["SELECT id FROM users;  "], conn)
    assert code == 0
    assert conn.sent == ["SELECT current_user", "BEGIN READ ONLY", "SET LOCAL statement_timeout = '5s'",
                         od._WRAPPED_QUERY, "ROLLBACK"]
    assert conn.params[3] == ("SELECT id FROM users", od.DEFAULT_ROWS + 1)
    assert conn.autocommit is True and conn.closed and lock.closed
    assert calls[0][1]["sslmode"] == "require"


def test_parse_table_xml_reads_real_postgres_output():
    """실제 PG 17 의 query_to_xml 출력(로컬에서 받아 적음) — 이름 되살리기 · 널 · 순서.
    Real PG 17 query_to_xml output: unescaped names, nulls, column order."""
    xml_text = ('<table xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n\n<row>\n'
                '  <_x003F_column_x003F_>1</_x003F_column_x003F_>\n  <b xsi:nil="true"/>\n'
                '  <t>2026-11-11T14:21:04</t>\n</row>\n\n</table>\n')
    assert od.parse_table_xml(xml_text) == (["?column?", "b", "t"], [("1", None, "2026-11-11T14:21:04")])
    assert od.parse_table_xml('<table xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n</table>') == ([], [])


def test_query_error_still_rolls_back_and_exits_2():
    """조회가 실패해도 ROLLBACK 을 보낸다 · exit 2 · 권한 거부면 허용 목록 위치를 알려 준다.
    A failing query still sends ROLLBACK; a permission error points at the allowlist."""
    conn = _Conn(error=_PgError("permission denied for table users", pgcode="42501"))
    code, out, _calls, _lock = _run(["SELECT email FROM users"], conn)
    assert code == 2
    assert conn.sent[-1] == "ROLLBACK"
    assert "0049_observer_role.py::_ALLOWED" in out


def test_audit_sends_only_catalog_reads_in_read_only_transactions():
    """--audit 는 정해 둔 카탈로그 조회만, 문장마다 BEGIN READ ONLY … ROLLBACK 으로 보낸다.
    --audit sends only the fixed catalog reads, each wrapped in BEGIN READ ONLY … ROLLBACK."""
    conn = _Conn(columns=("x",), rows=())
    code, out, _calls, _lock = _run(["--audit"], conn)
    assert code == 0
    queries = [p[0] for s, p in zip(conn.sent, conn.params) if s == od._WRAPPED_QUERY]
    assert queries == [sql for _title, sql in od._AUDIT]
    assert all(q.lstrip().upper().startswith("SELECT") for q in queries)
    assert conn.sent.count("BEGIN READ ONLY") == conn.sent.count("ROLLBACK") == len(od._AUDIT)
    assert "역할 속성" in out


# --- 2. 거부 — 아무것도 보내지 않는다 ------------------------------------------------


@pytest.mark.parametrize("url", [
    "postgresql://scamanager_app.abcref:pw@host:6543/postgres",
    "postgresql://scamanager_worker.abcref:pw@host:6543/postgres",
    "postgresql://postgres.abcref:pw@host:5432/postgres",
    "postgresql://scamanager_observer_admin.abcref:pw@host:6543/postgres",
    "postgresql://host:6543/postgres",
    # libpq 는 쿼리의 user= 를 주소의 사용자보다 앞세운다 / libpq lets a user= parameter override the URL user
    "postgresql://scamanager_observer.abcref:pw@host:6543/postgres?user=postgres",
    "postgresql://scamanager_observer.abcref:pw@host:6543/postgres?sslmode=require&user=",
])
def test_other_roles_are_refused_before_connecting(url):
    """관측 역할이 아닌 주소면 연결조차 하지 않는다(exit 1) / any other role: no connection at all."""
    code, _out, calls, _lock = _run(["SELECT 1"], _Conn(), url=url)
    assert code == 1
    assert calls == []


def test_connected_as_another_role_is_refused():
    """주소가 맞아도 서버의 current_user 가 다르면 조회하지 않는다 / server-side role must match too."""
    conn = _Conn(user="scamanager_app")
    code, _out, _calls, _lock = _run(["SELECT 1"], conn)
    assert code == 1
    assert conn.sent == ["SELECT current_user"]


def test_null_cells_print_as_null():
    code, out, _calls, _lock = _run(["SELECT a FROM t"], _Conn(columns=("a",), rows=((None,),)))
    assert code == 0 and "\nNULL\n" in out


def test_busy_lock_refuses_without_connecting():
    """다른 조회가 돌면 연결하지 않는다 / another run holds the lock: no connection."""
    code, _out, calls, _lock = _run(["SELECT 1"], _Conn(), lock_free=False)
    assert code == 1
    assert calls == []


def test_missing_url_exits_3(tmp_path):
    code, out, calls, _lock = _run(["SELECT 1"], _Conn(), url="", tmp_path=tmp_path)
    assert code == 3 and calls == []
    assert "observer_setup.py" in out


def test_sql_and_audit_are_exclusive():
    with pytest.raises(SystemExit):
        od.main(["SELECT 1", "--audit"], environ={od.ENV_KEY: _URL}, connect=lambda *a, **k: _Conn(),
                lock=_Lock, out=io.StringIO())


# --- 3. 출력 — 가림 · 상한 · 비밀번호 -------------------------------------------------


def test_cells_are_masked_flattened_and_cut():
    """셀은 비밀 꼴을 가리고(봇 URL · 웹훅 경로), 줄바꿈을 펴고, 300자로 자른다.
    Cells mask secret shapes, flatten newlines and cut at 300 characters."""
    rows = (("https://api.telegram.org/bot123456:ABCDEF/sendMessage", "line1\nline2\tx", "y" * 400),)
    code, out, _calls, _lock = _run(["SELECT a, b, c FROM t"], _Conn(columns=("a", "b", "c"), rows=rows))
    assert code == 0
    assert "123456:ABCDEF" not in out and "bot***" in out
    assert "line1 line2 x" in out
    assert "y" * 300 + "..." in out and "y" * 301 not in out


def test_rows_are_capped_with_a_note():
    rows = tuple((i,) for i in range(60))
    code, out, _calls, _lock = _run(["SELECT id FROM t"], _Conn(rows=rows))
    assert code == 0
    printed = [line for line in out.splitlines() if line.isdigit()]
    assert len(printed) == od.DEFAULT_ROWS
    assert "앞 50행만" in out


def test_password_is_never_printed_even_when_the_driver_echoes_the_dsn():
    """연결 오류 글에 주소가 실려도 비밀번호는 가려진다 / a DSN echoed in a connection error is masked."""
    code, out, _calls, _lock = _run(["SELECT 1"], _Conn(), connect_error=_PgError(f"could not connect: {_URL}"))
    assert code == 3
    assert _PW not in out


# --- 4. 주소 읽기 -------------------------------------------------------------------


def test_env_file_line_is_read_without_other_lines(tmp_path):
    """환경변수가 없으면 .env 의 그 줄 하나만 — 따옴표 · export · 주석 줄 처리.
    Without the env var, only that .env line is used (quotes, export prefix, commented duplicates)."""
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=postgresql://app:other@h/db\n"
                   f"# {od.ENV_KEY}=postgresql://old\n"
                   f"export {od.ENV_KEY}=\"{_URL}\"\n", encoding="utf-8")
    assert od.load_url({}, env) == _URL
    assert od.load_url({od.ENV_KEY: "postgresql://from-env"}, env) == "postgresql://from-env"
    assert od.load_url({}, tmp_path / "missing.env") is None


@pytest.mark.parametrize("url,role", [
    (_URL, "scamanager_observer"),
    ("postgresql://scamanager_observer:pw@localhost/db", "scamanager_observer"),
    ("postgresql+psycopg2://scamanager_observer.ref:pw@h/db", "scamanager_observer"),
    ("host=h user=scamanager_observer.ref password=pw dbname=postgres", "scamanager_observer"),
    ("postgresql://scamanager_observer_admin.ref:pw@h/db", "scamanager_observer_admin"),
    ("postgresql://scamanager_observer.ref:pw@h/db?user=postgres", "postgres"),
    ("postgresql://scamanager_observer.ref:pw@h/db?service=prod", ""),
    ("postgresql://h/db", ""),
    ("not a dsn at all ===", ""),
])
def test_url_role(url, role):
    assert od.url_role(url) == role


def test_lock_is_exclusive():
    """두 번째 잠금은 실패하고, 첫 잠금을 놓으면 다시 잡힌다 / the second acquire fails until the first is released."""
    first = od.acquire_lock(port=47999)
    assert first is not None
    try:
        assert od.acquire_lock(port=47999) is None
    finally:
        first.close()
    again = od.acquire_lock(port=47999)
    assert again is not None
    again.close()
