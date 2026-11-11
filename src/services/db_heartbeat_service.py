"""DB 쓰기 하트비트 — 풀의 서버 연결에 남은 세션 READ ONLY 를 1분 안에 되돌리고, 쓰기가 막히면 알린다 (회고 원장 L02).
DB write heartbeat: undo a session-level READ ONLY stuck on a pooled server connection within a minute,
and alert when writes stay blocked (retro ledger L02, layer 3).

🔴 2026-10-25 — 워커 풀(Supavisor 트랜잭션 모드)로 들어온 `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY`
가 그 풀의 하나뿐인 서버 연결에 남아, 분석 저장 · 로그인을 포함한 워커 쓰기가 25시간 실패했다.
진단은 `pg_settings.source = 'session'`, 복구는 같은 풀로 보낸 `RESET default_transaction_read_only` 였다.

매 분, 웹 · 워커 풀마다 트랜잭션 하나로 잰다(그 안에서는 서버 연결이 고정된다). 설정만 읽는다.
1. `default_transaction_read_only` 가 `on` 이고 출처가 `session` 이면 `RESET` 한 뒤 COMMIT 한다. 그 연결만
   기본값으로 돌아가고, 한 번 알린다. 데이터베이스 · 역할 · 설정 파일 출처(예: Supabase 디스크 보호)는 건드리지 않는다.
2. 아니면 `transaction_read_only` 를 본다 — 25006 은 정확히 이 값이 `on` 일 때 난다(출처가 세션 · DB · 역할이든
   hot standby 든). `on` 이 연속 `ALERT_AFTER` 번이면 한 번 알리고, 회복하면 한 번 더 알린다. 끝은 ROLLBACK.
🔴 쓰기를 시도하지 않는다 — `UPDATE … WHERE false` 도 표 단위 RowExclusiveLock 을 ROLLBACK 까지 쥐어, 그 사이
   클라이언트가 멈추면 마이그레이션의 `CREATE INDEX` 를 세운다(Grok 반례 38408243). 설정 읽기는 앱 테이블을 잠그지 않는다.
상태(연속 실패 수)는 프로세스 메모리에 둔다 — 운영은 단일 인스턴스다(`src/scheduler.py` 한계 절).

Every minute, per pool, one settings-only transaction (the server connection is pinned inside it): a
session-sourced `default_transaction_read_only = on` is RESET and committed (only that connection returns to its
default); otherwise `transaction_read_only` tells whether writes would fail with 25006. No write is attempted, so
no lock is taken on any application table. Other sources are never touched.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.database import SessionLocal, WorkerSessionLocal
from src.notifier.telegram import telegram_post_message
from src.shared.alembic_dialect import is_postgresql
from src.shared.http_client import HTTPX_SEND_ERRORS
from src.shared.off_loop import run_blocking

logger = logging.getLogger(__name__)

ALERT_AFTER = 3  # 연속 실패 수 — 1분 주기라 3분 / consecutive failures (3 minutes at the 1-minute cadence)

_TIMEOUT = text("SET LOCAL statement_timeout = '5s'")
# 이 트랜잭션이 읽기 전용인가(= 쓰기가 25006 으로 막히는가) · 기본값과 그 출처 / is this transaction read-only, and why
PROBE = text("SELECT current_setting('transaction_read_only'), setting, source "
             "FROM pg_settings WHERE name = 'default_transaction_read_only'")
_RESET = text("RESET default_transaction_read_only")


@dataclass
class _PoolState:
    failures: int = 0
    alerted: bool = False


_STATE: dict[str, _PoolState] = {}


def probe(session_factory) -> tuple[str, str | None]:
    """풀 하나를 한 번 잰다 → (결과, 실패 사유). 결과 = `ok` · `healed`(세션 READ ONLY 를 되돌림) ·
    `failed`(읽기 전용이면 `read-only:<출처>`, DB 오류면 SQLSTATE · 없으면 예외 이름) · `skipped`(PostgreSQL 아님).
    One check of one pool → (outcome, failure reason)."""
    db = session_factory()
    try:
        if not is_postgresql(db.get_bind()):
            return "skipped", None
        db.execute(_TIMEOUT)
        transaction_read_only, default, source = db.execute(PROBE).one()
        if default == "on" and source == "session":
            db.execute(_RESET)
            db.commit()
            return "healed", None
        if transaction_read_only == "on":
            return "failed", f"read-only:{source}"
        return "ok", None
    except SQLAlchemyError as exc:
        orig = getattr(exc, "orig", None)
        return "failed", getattr(orig, "pgcode", None) or type(orig or exc).__name__
    finally:
        db.rollback()
        db.close()


async def _notify(message: str) -> None:
    """운영자 채팅으로 한 줄 — 실패해도 하트비트는 계속 돈다 / one line to the operator chat; never raises."""
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        return
    try:
        await telegram_post_message(settings.telegram_bot_token, settings.telegram_chat_id, {"text": message})
    except (*HTTPX_SEND_ERRORS, KeyError, ValueError) as exc:
        logger.warning("db heartbeat telegram alert failed: %s", type(exc).__name__)


async def _account(pool: str, outcome: str, code: str | None) -> None:
    state = _STATE.setdefault(pool, _PoolState())
    if outcome == "healed":
        logger.warning("db heartbeat: reset a session-level READ ONLY on the %s pool", pool)
        await _notify(f"🩹 DB {pool} 풀 — 서버 연결에 남은 세션 READ ONLY 를 되돌렸다(RESET). "
                      f"누가 이 풀로 SET SESSION 을 보냈는지 확인한다. / reset a session-level READ ONLY.")
        state.failures, state.alerted = 0, False
        return
    if outcome in ("ok", "skipped"):
        if state.alerted:
            await _notify(f"✅ DB {pool} 풀 쓰기 회복 / writes recovered.")
        state.failures, state.alerted = 0, False
        return
    state.failures += 1
    logger.warning("db heartbeat failed: pool=%s code=%s consecutive=%d", pool, code, state.failures)
    if state.failures >= ALERT_AFTER and not state.alerted:
        await _notify(f"🚨 DB {pool} 풀 쓰기 불가 {state.failures}분 연속 ({code}). "
                      "read-only 출처가 database · configuration file 이면 Supabase 디스크 보호 같은 플랫폼 쪽이다. "
                      "/ writes blocked.")
        state.alerted = True


async def run_db_heartbeat(pools=None) -> dict[str, str]:
    """웹 · 워커 풀을 한 번씩 잰다(동기 DB 는 워커 스레드에서) → {풀: 결과[:코드]}.
    Probe the web and worker pools once each (sync DB in a worker thread)."""
    pools = pools if pools is not None else {"web": SessionLocal, "worker": WorkerSessionLocal}
    results: dict[str, str] = {}
    for pool, factory in pools.items():
        outcome, code = await run_blocking(probe, factory)
        results[pool] = outcome if code is None else f"{outcome}:{code}"
        await _account(pool, outcome, code)
    return results
