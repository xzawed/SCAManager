"""DB 쓰기 하트비트 — 세션 READ ONLY 만 되돌리고, 다른 출처는 건드리지 않으며, 막히면 한 번 알린다 (회고 원장 L02).
DB write heartbeat: undo only a session-level READ ONLY, never touch other sources, alert once when blocked.

가짜 세션으로 «보내는 문장» 과 «알림 횟수» 를 잰다. 실제 풀 연결 오염 · 회복은
tests/integration/test_db_heartbeat_postgres.py 가 실 PostgreSQL 로 잰다.
A fake session measures statements and alert counts; real pool poisoning is measured on PostgreSQL.
"""
# pylint: disable=redefined-outer-name
import pytest
from sqlalchemy.exc import OperationalError

from src.services import db_heartbeat_service as hb


class _PgError(Exception):
    def __init__(self, pgcode):
        super().__init__(pgcode)
        self.pgcode = pgcode


class _Result:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


class _Bind:
    def __init__(self, name):
        self.dialect = type("D", (), {"name": name})()


class _Session:
    """설정 한 줄(transaction_read_only, 기본값, 출처)을 돌려주는 가짜 세션 / fake session returning the settings row."""

    def __init__(self, row=("off", "off", "default"), db_error=None, dialect="postgresql"):
        self.row, self.db_error, self.dialect = row, db_error, dialect
        self.sent, self.committed, self.rolled_back, self.closed = [], False, False, False

    def get_bind(self):
        return _Bind(self.dialect)

    def execute(self, statement):
        sql = str(statement)
        self.sent.append(sql)
        if "pg_settings" in sql:
            if self.db_error is not None:
                raise OperationalError(sql, {}, _PgError(self.db_error))
            return _Result(self.row)
        return _Result(None)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


_POISONED = ("on", "on", "session")      # 2026-10-25 꼴 / the incident shape
_DB_READ_ONLY = ("on", "on", "database")  # Supabase 디스크 보호 같은 플랫폼 쪽 / platform-imposed


@pytest.fixture(autouse=True)
def _fresh_state(monkeypatch):
    monkeypatch.setattr(hb, "_STATE", {})
    sent = []

    async def fake_post(token, chat, payload):
        sent.append(payload["text"])

    monkeypatch.setattr(hb, "telegram_post_message", fake_post)
    monkeypatch.setattr(hb.settings, "telegram_bot_token", "123:ABC")
    monkeypatch.setattr(hb.settings, "telegram_chat_id", "-100123")
    return sent


# --- 1. 한 번 재기 -------------------------------------------------------------------


def test_healthy_pool_reads_settings_only_and_rolls_back():
    """정상 — 시간 제한 → 설정 한 줄 읽기 → ROLLBACK. 쓰기 · RESET · COMMIT 은 없다(앱 테이블을 잠그지 않는다).
    Healthy: timeout, one settings read, ROLLBACK; no write, RESET or COMMIT (no application table is locked)."""
    session = _Session()
    assert hb.probe(lambda: session) == ("ok", None)
    assert session.sent == ["SET LOCAL statement_timeout = '5s'", str(hb.PROBE)]
    assert "UPDATE" not in str(hb.PROBE).upper() and "repositories" not in str(hb.PROBE)
    assert not session.committed and session.rolled_back and session.closed


def test_session_level_read_only_is_reset_and_committed():
    """세션 출처의 READ ONLY — RESET 후 COMMIT 으로 그 연결만 되돌린다.
    A session-sourced READ ONLY is RESET and committed on that connection."""
    session = _Session(row=_POISONED)
    assert hb.probe(lambda: session) == ("healed", None)
    assert session.sent[-1] == "RESET default_transaction_read_only"
    assert session.committed


@pytest.mark.parametrize("row,reason", [
    (("on", "on", "database"), "read-only:database"),
    (("on", "on", "user"), "read-only:user"),
    (("on", "on", "configuration file"), "read-only:configuration file"),
    # hot standby — 기본값은 off 인데 트랜잭션이 읽기 전용 / hot standby: default off, transaction read-only
    (("on", "off", "default"), "read-only:default"),
])
def test_other_read_only_sources_are_reported_never_reset(row, reason):
    """세션이 아닌 출처는 RESET 하지 않는다 — 쓰기가 막혔다고만 보고한다.
    Non-session sources are never RESET; the probe only reports the block."""
    session = _Session(row=row)
    assert hb.probe(lambda: session) == ("failed", reason)
    assert "RESET default_transaction_read_only" not in session.sent
    assert not session.committed and session.rolled_back


def test_db_error_reports_its_sqlstate():
    session = _Session(db_error="57P01")
    assert hb.probe(lambda: session) == ("failed", "57P01")
    assert session.rolled_back and session.closed


def test_non_postgres_is_skipped():
    session = _Session(dialect="sqlite")
    assert hb.probe(lambda: session) == ("skipped", None)
    assert session.sent == []


# --- 2. 알림 — 연속 실패에 한 번, 회복에 한 번, 되돌렸으면 한 번 ------------------------------


async def _beat(outcomes, sent):
    """풀 하나에 결과를 차례로 흘려 보내고, 알림 글을 돌려준다 / feed outcomes for one pool, return alerts."""
    for outcome in outcomes:
        session = {"ok": _Session(), "fail": _Session(row=_DB_READ_ONLY), "heal": _Session(row=_POISONED)}[outcome]
        await hb.run_db_heartbeat(pools={"worker": lambda s=session: s})
    return list(sent)


async def test_alert_once_after_three_failures_then_recovery(_fresh_state):
    alerts = await _beat(["fail", "fail", "ok", "fail", "fail", "fail", "fail", "ok"], _fresh_state)
    assert len(alerts) == 2, alerts
    assert alerts[0].startswith("🚨 DB worker") and "read-only:database" in alerts[0]
    assert alerts[1].startswith("✅ DB worker")


async def test_heal_is_reported_once_per_event(_fresh_state):
    alerts = await _beat(["heal", "ok", "heal"], _fresh_state)
    assert [a.split()[0] for a in alerts] == ["🩹", "🩹"]


async def test_results_name_each_pool_and_code():
    results = await hb.run_db_heartbeat(pools={"web": lambda: _Session(),
                                               "worker": lambda: _Session(row=_DB_READ_ONLY)})
    assert results == {"web": "ok", "worker": "failed:read-only:database"}


async def test_telegram_failure_never_raises(monkeypatch, _fresh_state):
    async def broken(token, chat, payload):
        raise ValueError("boom")

    monkeypatch.setattr(hb, "telegram_post_message", broken)
    await _beat(["heal"], _fresh_state)  # 예외 없이 끝난다 / completes without raising


async def test_no_alert_without_operator_chat(monkeypatch, _fresh_state):
    monkeypatch.setattr(hb.settings, "telegram_chat_id", "")
    alerts = await _beat(["fail", "fail", "fail", "heal"], _fresh_state)
    assert alerts == []
