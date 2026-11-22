"""claude_api_calls.cost_usd — 판 단위 요율이 생긴 판의 과거 행을 그 요율로 다시 매긴다

claude_api_calls.cost_usd — re-price past rows of models that now have their own rate.

Revision ID: 0052
Revises: 0051

요율이 계열 단위였을 때 새 세대 판의 행은 그 계열의 옛 요율로 매겨졌다(예: Haiku 5.5 를 Haiku 4.5 의 $1/$5 로 — 10배).
판 단위 요율(#1905 ② — `src/shared/claude_metrics.py::_MODEL_RATES`)이 들어오면 그 판은 «확정» 요율인데 저장된 비용은 옛
요율 그대로라, 요율이 바뀐 판의 행을 새 요율로 다시 매긴다. 요율은 이 파일에 고정한다 — 앱 요율표가 나중에 바뀌어도
이 이전이 내는 값은 그대로다.

- 대상 = 요율이 바뀐 다섯 판(별칭 · 날짜 붙은 id). 비슷하지만 다른 이름(`…-preview`)과 다른 판은 그대로 둔다.
- 되돌리기는 ② 전의 계열 요율로 다시 매긴다(haiku $1/$5 · sonnet $2/$10 · opus $5/$25 · fable $10/$50 · 캐시 읽기 = 입력 × 0.1).
- PostgreSQL 에서 이 역할이 RLS 를 우회하지 못하면 보이는 행만 바뀐다 — 경고만 남긴다. 안 바뀐 행은 옛 요율의 비용일 뿐이라
  배포를 막지 않는다.
Re-prices the five models whose rate changed (aliases and dated ids), with rates frozen in this file; the downgrade
restores the old line rates. A role that cannot bypass RLS only re-prices the rows it sees and logs a warning.
"""
from __future__ import annotations

import logging
import re

import sqlalchemy as sa
from alembic import op

from src.shared.alembic_dialect import is_postgresql

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")

_DATED_SUFFIX = re.compile(r"-\d{8}$")
# 이 이전이 읽고 쓰는 열만 — 문자열 SQL 없이 조건을 만든다 / just the columns this migration touches
_CALLS = sa.table(
    "claude_api_calls", sa.column("id"), sa.column("model"), sa.column("input_tokens"), sa.column("output_tokens"),
    sa.column("cache_read_tokens"), sa.column("cache_creation_tokens"), sa.column("cost_usd"),
)
_CACHE_READ_DEFAULT = 0.1   # 표에 캐시 읽기가 없으면 입력 × 0.1 / without a cache-read rate: input × 0.1
_CACHE_WRITE = 1.25         # 캐시 쓰기 = 입력 × 1.25(5분) / cache write: input × 1.25 (5-minute)

# 판 → (입력, 출력, 캐시 읽기 | None, 구간 경계 | None, 구간 입력, 구간 출력) — USD / 1M 토큰 (Anthropic 2026-11)
# model -> (input, output, cache read | None, tier threshold | None, tier input, tier output), USD per 1M tokens
NEW_RATES: dict[str, tuple] = {
    "claude-haiku-5-5": (0.10, 0.50, None, 100_000, 0.50, 2.50),
    "claude-sonnet-5-5": (2.0, 10.0, 0.10, None, None, None),
    "claude-opus-5-5": (4.0, 20.0, 0.20, None, None, None),
    "claude-fable-5-1": (10.0, 50.0, 0.25, None, None, None),
    "claude-fable-5-2": (8.0, 40.0, 0.20, None, None, None),
}
# ② 전의 계열 요율 — 그때 이 판들이 매겨진 값 / the line rates these models were priced at before ②
OLD_RATES: dict[str, tuple] = {
    "claude-haiku-5-5": (1.0, 5.0, None, None, None, None),
    "claude-sonnet-5-5": (2.0, 10.0, None, None, None, None),
    "claude-opus-5-5": (5.0, 25.0, None, None, None, None),
    "claude-fable-5-1": (10.0, 50.0, None, None, None, None),
    "claude-fable-5-2": (10.0, 50.0, None, None, None, None),
}


def cost_usd(rate: tuple, input_tokens: int, output_tokens: int, cache_read: int, cache_creation: int) -> float:
    """행 하나의 비용 — 구간은 프롬프트(입력 + 캐시 읽기 + 캐시 쓰기) 길이로 요청 전체에 건다.

    One row's cost; a tier applies to the whole request by prompt size (input + cache reads + cache writes).
    """
    in_rate, out_rate, read_rate, threshold, tier_in, tier_out = rate
    if threshold is not None and input_tokens + cache_read + cache_creation > threshold:
        in_rate, out_rate, read_rate = tier_in, tier_out, None
    read = read_rate if read_rate is not None else in_rate * _CACHE_READ_DEFAULT
    return (input_tokens * in_rate + output_tokens * out_rate + cache_read * read
            + cache_creation * in_rate * _CACHE_WRITE) / 1_000_000


def _reprice(conn, rates: dict[str, tuple]) -> int:
    """대상 판(별칭 또는 날짜 붙은 id)의 행을 `rates` 로 다시 매긴다 — 바꾼 행 수를 돌려준다.

    Re-price rows of the target models (alias or dated id) with `rates`; returns the number of rows changed.
    """
    calls = _CALLS
    targets = sa.or_(*(sa.or_(calls.c.model == model, calls.c.model.like(f"{model}-%")) for model in rates))
    rows = conn.execute(sa.select(calls.c.id, calls.c.model, calls.c.input_tokens, calls.c.output_tokens,
                                  calls.c.cache_read_tokens, calls.c.cache_creation_tokens).where(targets)).all()
    changed = 0
    for row in rows:
        rate = rates.get(_DATED_SUFFIX.sub("", row.model))
        if rate is None:
            continue  # `…-preview` 처럼 접두가 같은 다른 이름 / a different name sharing the prefix
        conn.execute(sa.update(calls).where(calls.c.id == row.id).values(cost_usd=cost_usd(
            rate, row.input_tokens or 0, row.output_tokens or 0, row.cache_read_tokens or 0,
            row.cache_creation_tokens or 0)))
        changed += 1
    return changed


def _warn_if_rls_may_hide_rows(conn) -> None:
    """PostgreSQL 에서 현재 역할이 RLS 를 우회하지 못하면 경고 — 그 역할에겐 일부 행만 보인다."""
    if not is_postgresql(conn):
        return
    bypass = conn.execute(sa.text(
        "SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")).scalar()
    if not bypass:
        logger.warning("0052: 이 역할은 RLS 를 우회하지 못한다 — 보이는 비용 행만 다시 매긴다(나머지는 옛 요율 값)")


def upgrade() -> None:
    conn = op.get_bind()
    _warn_if_rls_may_hide_rows(conn)
    logger.info("0052: claude_api_calls 판 단위 요율로 다시 매김 — %d행", _reprice(conn, NEW_RATES))


def downgrade() -> None:
    conn = op.get_bind()
    _warn_if_rls_may_hide_rows(conn)
    logger.info("0052: claude_api_calls 옛 계열 요율로 되돌림 — %d행", _reprice(conn, OLD_RATES))
