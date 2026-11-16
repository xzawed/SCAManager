"""0050 — 리포 설정에 고정된 Haiku 날짜 스냅샷 id 를 별칭으로 옮긴다 (회고 원장 이관 K11 P2-38 · P2-55).

이 파일은 기존 행을 심고 마이그레이션의 이름 바꾸기 함수를 **직접 호출**해, 바꿀 행만 바뀌고 나머지(별칭 · 다른 모델 ·
NULL · 비슷하지만 다른 문자열)는 그대로인지, 되돌리기가 역으로 도는지 본다. 빈 테이블에서 도는 CI PG 왕복은 이 갈래를
돌리지 않는다.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, text
from sqlalchemy.pool import StaticPool

_ROOT = Path(__file__).resolve().parents[3]
_REV = _ROOT / "alembic" / "versions" / "0050_review_model_haiku_alias.py"

_DATED = "claude-haiku-4-5-20251001"
_ALIAS = "claude-haiku-4-5"

# witness-corpus: 바꿀 값 · 이미 별칭 · 다른 모델 · NULL · 앞뒤가 다른 비슷한 문자열
_SEED = {
    1: _DATED,
    2: _DATED,
    3: _ALIAS,
    4: "claude-sonnet-5",
    5: None,
    6: "claude-haiku-4-5-20251001-preview",
    7: " claude-haiku-4-5-20251001",
}


def _module():
    spec = importlib.util.spec_from_file_location("rev0050", _REV)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(name="db")
def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    meta = MetaData()
    Table("repo_configs", meta,
          Column("id", Integer, primary_key=True),
          Column("repo_full_name", String(255)),
          Column("review_model", String(50), nullable=True))
    meta.create_all(engine)
    with engine.begin() as conn:
        for row_id, model in _SEED.items():
            conn.execute(text("INSERT INTO repo_configs (id, repo_full_name, review_model) VALUES (:i, :n, :m)"),
                         {"i": row_id, "n": f"o/r{row_id}", "m": model})
    yield engine
    engine.dispose()


def _models(engine) -> dict:
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT id, review_model FROM repo_configs ORDER BY id")).all())


def test_the_constants_name_the_two_ids():
    mod = _module()
    assert (mod.DATED_ID, mod.ALIAS_ID) == (_DATED, _ALIAS)


def test_upgrade_moves_only_the_dated_id(db):
    """🔴 정확히 날짜 id 인 행만 별칭이 된다 — 이미 별칭 · 다른 모델 · NULL · 비슷한 문자열은 그대로."""
    mod = _module()
    with db.begin() as conn:
        moved = mod._rename(conn, _DATED, _ALIAS)  # pylint: disable=protected-access
    assert moved == 2, moved
    expected = dict(_SEED)
    expected[1] = expected[2] = _ALIAS
    assert _models(db) == expected


def test_downgrade_reverses_the_rename(db):
    """되돌리기는 별칭을 날짜 id 로 — 같은 모델이라 원래 별칭이던 행도 날짜 id 가 되는 것은 감수한다(독스트링)."""
    mod = _module()
    with db.begin() as conn:
        mod._rename(conn, _DATED, _ALIAS)  # pylint: disable=protected-access
    with db.begin() as conn:
        back = mod._rename(conn, _ALIAS, _DATED)  # pylint: disable=protected-access
    assert back == 3, back
    models = _models(db)
    assert models[1] == models[2] == models[3] == _DATED
    assert models[4] == "claude-sonnet-5" and models[5] is None


def test_the_rename_is_idempotent(db):
    mod = _module()
    with db.begin() as conn:
        mod._rename(conn, _DATED, _ALIAS)  # pylint: disable=protected-access
    first = _models(db)
    with db.begin() as conn:
        again = mod._rename(conn, _DATED, _ALIAS)  # pylint: disable=protected-access
    assert again == 0 and _models(db) == first
