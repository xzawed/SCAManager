"""0052 — 판 단위 요율이 생긴 판의 과거 비용 행을 그 요율로 다시 매긴다 (Issue #1905 ②).

기존 행을 심고 마이그레이션의 다시 매기기 함수를 **직접 호출**해, 대상 판(별칭 · 날짜 붙은 id)만 바뀌고 나머지(비슷하지만
다른 이름 · 다른 판)는 그대로인지, 새 값이 앱의 요율 함수와 같은지, 되돌리기가 옛 계열 요율로 돌아가는지 본다.
빈 테이블에서 도는 CI PG 왕복은 이 갈래를 돌리지 않는다.
Seeds rows and calls the migration's re-pricing directly: only target models change, new values match the app's
pricing function, and the downgrade restores the old line rates.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.pool import StaticPool

from src.shared.claude_metrics import estimate_claude_cost_usd

_ROOT = Path(__file__).resolve().parents[3]
_REV = _ROOT / "alembic" / "versions" / "0052_reprice_claude_calls_by_model.py"

# witness-corpus: 대상 판(별칭 · 날짜 id · 구간 넘김 · 캐시 읽기) · 비슷하지만 다른 이름 · 대상 밖 판
# (id, model, input, output, cache_read, cache_creation, 저장된 옛 비용)
_SEED = [
    (1, "claude-haiku-5-5", 215, 9, 0, 0, 0.000260),
    (2, "claude-haiku-5-5", 150_000, 1_000, 0, 0, 0.155),
    (3, "claude-sonnet-5-5", 1_000, 100, 50_000, 0, 0.013),
    (4, "claude-opus-5-5", 1_000, 1_000, 0, 2_000, 0.0425),
    (5, "claude-fable-5-2", 1_000, 1_000, 1_000, 0, 0.061),
    (6, "claude-opus-5-5-20261001", 10_000, 0, 0, 0, 0.05),
    (7, "claude-sonnet-5-5-preview", 1_000, 0, 0, 0, 0.002),
    (8, "claude-sonnet-5", 1_000, 0, 0, 0, 0.002),
    (9, "claude-haiku-4-5-20251001", 1_000, 0, 0, 0, 0.001),
    (10, "claude-fable-5-1", 0, 0, 1_000_000, 0, 1.0),
]
_TARGET_IDS = {1, 2, 3, 4, 5, 6, 10}


def _module():
    spec = importlib.util.spec_from_file_location("rev0052", _REV)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


@pytest.fixture(name="db")
def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    meta = MetaData()
    Table("claude_api_calls", meta,
          Column("id", Integer, primary_key=True),
          Column("model", String(64), nullable=False),
          Column("input_tokens", Integer, nullable=False),
          Column("output_tokens", Integer, nullable=False),
          Column("cache_read_tokens", Integer, nullable=False),
          Column("cache_creation_tokens", Integer, nullable=False),
          Column("cost_usd", Float, nullable=False))
    meta.create_all(engine)
    with engine.begin() as conn:
        for row in _SEED:
            conn.execute(text(
                "INSERT INTO claude_api_calls (id, model, input_tokens, output_tokens, cache_read_tokens, "
                "cache_creation_tokens, cost_usd) VALUES (:i, :m, :inp, :out, :cr, :cc, :cost)"),
                dict(zip(("i", "m", "inp", "out", "cr", "cc", "cost"), row)))
    yield engine
    engine.dispose()


def _costs(engine) -> dict[int, float]:
    with engine.connect() as conn:
        return {row.id: row.cost_usd for row in conn.execute(text("SELECT id, cost_usd FROM claude_api_calls"))}


def _app_cost(row) -> float:
    _, model, inp, out, cache_read, cache_creation, _ = row
    return estimate_claude_cost_usd(model=model, input_tokens=inp, output_tokens=out,
                                    cache_read_tokens=cache_read, cache_creation_tokens=cache_creation)


def test_upgrade_reprices_only_target_models_at_the_app_rate(db):
    rev = _module()
    with db.begin() as conn:
        changed = rev._reprice(conn, rev.NEW_RATES)  # pylint: disable=protected-access
    after = _costs(db)
    assert changed == len(_TARGET_IDS)
    for row in _SEED:
        if row[0] in _TARGET_IDS:
            # 이전이 고정한 요율 == 앱 요율표 — 둘이 어긋나면 화면과 저장값이 다른 비용을 말한다
            # The migration's frozen rates equal the app table; a drift would make screen and storage disagree.
            assert after[row[0]] == pytest.approx(_app_cost(row)), row[1]
        else:
            assert after[row[0]] == row[6], row[1]
    assert after[1] == pytest.approx((215 * 0.10 + 9 * 0.50) / 1e6)          # 운영의 그 1행 / the production row
    assert after[2] == pytest.approx((150_000 * 0.50 + 1_000 * 2.50) / 1e6)  # 구간을 넘긴 요청 전체 / tiered


def test_downgrade_restores_the_old_line_rates(db):
    rev = _module()
    with db.begin() as conn:
        rev._reprice(conn, rev.NEW_RATES)  # pylint: disable=protected-access
        rev._reprice(conn, rev.OLD_RATES)  # pylint: disable=protected-access
    after = _costs(db)
    # ② 전의 계열 요율: haiku 1/5 · sonnet 2/10 · opus 5/25 · fable 10/50 · 캐시 읽기 = 입력 × 0.1 · 쓰기 × 1.25
    assert after[1] == pytest.approx((215 * 1.0 + 9 * 5.0) / 1e6)
    assert after[3] == pytest.approx((1_000 * 2.0 + 100 * 10.0 + 50_000 * 0.2) / 1e6)
    assert after[4] == pytest.approx((1_000 * 5.0 + 1_000 * 25.0 + 2_000 * 5.0 * 1.25) / 1e6)
    assert after[10] == pytest.approx(1_000_000 * 10.0 * 0.1 / 1e6)
    assert after[7] == 0.002 and after[8] == 0.002  # 대상 밖은 끝까지 그대로 / untouched throughout


def test_the_upgrade_and_downgrade_entry_points_use_their_own_rates(db, monkeypatch):
    # 진입점이 표를 바꿔 잡으면(upgrade 가 옛 요율 · downgrade 가 새 요율) 위 두 시험은 못 본다
    # The entry points themselves: swapping the tables inside upgrade/downgrade would pass the tests above.
    from types import SimpleNamespace  # pylint: disable=import-outside-toplevel

    rev = _module()
    with db.begin() as conn:
        monkeypatch.setattr(rev, "op", SimpleNamespace(get_bind=lambda: conn))
        rev.upgrade()
    assert _costs(db)[1] == pytest.approx((215 * 0.10 + 9 * 0.50) / 1e6)
    with db.begin() as conn:
        monkeypatch.setattr(rev, "op", SimpleNamespace(get_bind=lambda: conn))
        rev.downgrade()
    assert _costs(db)[1] == pytest.approx((215 * 1.0 + 9 * 5.0) / 1e6)


def test_cache_writes_count_toward_the_haiku_tier_in_the_migration():
    rev = _module()
    rate = rev.NEW_RATES["claude-haiku-5-5"]
    assert rev.cost_usd(rate, 60_000, 0, 0, 60_000) == pytest.approx((60_000 * 0.50 + 60_000 * 0.50 * 1.25) / 1e6)
    assert rev.cost_usd(rate, 100_001, 0, 0, 0) == pytest.approx(100_001 * 0.50 / 1e6)
