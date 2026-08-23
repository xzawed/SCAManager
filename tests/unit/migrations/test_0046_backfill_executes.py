"""🔴 0046 백필이 **실제로 돌면서 파이썬 판정과 같은 값**을 쓰는가.

🔴 Whether the 0046 backfill actually runs and writes exactly the Python verdict.

## 왜 이 파일이 따로 있나 (Grok claim-review `01a02f70` Q1·Q5-11)

0046 을 검증하던 축은 셋 다 백필 **로직을 돌리지 않았다**:

  · 소스 스캔 — 「파일에 `score_is_unreliable` 문자열이 있는가」
  · `upgrade head` (PG job) — **빈 테이블**에서 돌아 루프가 0회
  · PG 평균 테스트 — 시드가 이미 캐시를 채워 둔다

즉 이 마이그레이션을 파이썬으로 짠 **바로 그 이유**(판정을 SQL 로 복제하지 않는다)가
한 번도 실행되지 않았다. 판정이 JSON 불린 `"false"` 를 truthy 로 보는 것 같은 미묘한
지점은 SQL 복제와 갈리는데, 그 갈림을 아무도 재지 않았다.

이 파일은 기존 행을 심고 **백필 함수를 직접 호출**해 전 행을 대조한다.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from sqlalchemy import Boolean, Column, Integer, JSON, MetaData, Table, create_engine, text
from sqlalchemy.pool import StaticPool

from src.scorer.reliability import score_is_unreliable

_ROOT = Path(__file__).resolve().parents[3]
_REV = _ROOT / "alembic" / "versions" / "0046_analysis_score_unreliable.py"


def _module():
    spec = importlib.util.spec_from_file_location("rev0046", _REV)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 🔴 판정이 갈릴 수 있는 형태를 일부러 섞는다 — SQL 복제였다면 여기서 갈렸을 것들.
_ROWS = [
    {"ai_review_status": "success"},                        # 신뢰 O
    {"ai_review_status": "api_error"},                      # X — 위임 함수
    {"ai_review_status": "disabled"},                       # X — frozenset
    {"static_analysis_incomplete": True},                   # X
    {"static_analysis_incomplete": "false"},                # 🔴 X — 문자열이라 truthy
    {"source": "cli"},                                      # X
    {"source": "pr"},                                       # O
    {"breakdown": {"ai_defaults_applied": True}},           # X
    {"breakdown": {"ai_defaults_applied": False}},          # O
    {"breakdown": {"ai_defaults_applied": 1}},              # 🔴 X — truthy 판정
    {"breakdown": "not-a-dict"},                            # O — isinstance 분기
    {"static_uncovered_languages": ["rust"]},               # X
    {"static_uncovered_languages": []},                     # O
    {},                                                     # O
    None,                                                   # O — 빈 result
]


@pytest.fixture(name="db")
def _db():
    """`analyses` 최소 형상 + 컬럼이 **이미 추가된** 상태(백필 직전 시점)."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    meta = MetaData()
    Table(
        "analyses", meta,
        Column("id", Integer, primary_key=True),
        Column("result", JSON),
        # add_column 직후 = 전 행이 server_default(true) 상태
        Column("score_unreliable", Boolean, nullable=False, server_default=text("true")),
    )
    meta.create_all(engine)
    with engine.begin() as conn:
        for i, result in enumerate(_ROWS, start=1):
            conn.execute(
                text("INSERT INTO analyses (id, result, score_unreliable)"
                     " VALUES (:i, :r, 1)"),
                {"i": i, "r": json.dumps(result) if result is not None else None},
            )
    yield engine
    engine.dispose()


def test_the_sample_is_not_one_sided():
    """공허화 차단 — 두 판정이 다 있어야 백필이 검증된다."""
    verdicts = {score_is_unreliable(r) for r in _ROWS}
    assert verdicts == {True, False}, f"표본이 한쪽뿐: {verdicts}"


def test_backfill_writes_exactly_the_python_verdict(db):
    """🔴 실경로 — 백필을 **호출**해 전 행이 판정과 같아지는지 본다."""
    mod = _module()
    with db.begin() as conn:
        updated = mod._backfill(conn)  # pylint: disable=protected-access
    assert updated == len(_ROWS), f"갱신 행 수 {updated} != {len(_ROWS)}"

    with db.connect() as conn:
        rows = conn.execute(text("SELECT id, result, score_unreliable FROM analyses ORDER BY id")).all()

    mismatches = []
    for row_id, raw, flag in rows:
        source = _ROWS[row_id - 1]
        expected = score_is_unreliable(source)
        if bool(flag) != expected:
            mismatches.append(f"id={row_id} {source!r}: 기대 {expected} 실제 {bool(flag)}")
    assert not mismatches, (
        "백필이 판정과 다른 값을 썼다 — SQL 로 판정을 복제했다면 나올 형태다:\n  "
        + "\n  ".join(mismatches)
    )


def test_backfill_clears_the_fail_closed_default_where_appropriate(db):
    """🔴 기본값 true 가 백필로 **정확히** 걷히는가.

    시드는 전 행이 `true`(fail-closed 기본값)다. 백필 후 신뢰 가능한 행만 `false` 가
    돼야 한다 — 전부 true 로 남으면 평균이 텅 비고, 전부 false 면 기본값이 무의미해진다.
    """
    mod = _module()
    with db.begin() as conn:
        mod._backfill(conn)  # pylint: disable=protected-access
    with db.connect() as conn:
        flipped = conn.execute(text(
            "SELECT count(*) FROM analyses WHERE score_unreliable = 0")).scalar()
    expected = sum(1 for r in _ROWS if not score_is_unreliable(r))
    assert flipped == expected, f"false 로 바뀐 행 {flipped} != 기대 {expected}"
    assert 0 < expected < len(_ROWS), "표본이 한쪽으로 쏠려 이 축이 공허하다"


def test_backfill_is_idempotent(db):
    """두 번 돌려도 같은 결과 — 재배포·재실행이 값을 흔들지 않는다."""
    mod = _module()
    with db.begin() as conn:
        mod._backfill(conn)  # pylint: disable=protected-access
    with db.connect() as conn:
        first = conn.execute(text("SELECT id, score_unreliable FROM analyses ORDER BY id")).all()
    with db.begin() as conn:
        mod._backfill(conn)  # pylint: disable=protected-access
    with db.connect() as conn:
        second = conn.execute(text("SELECT id, score_unreliable FROM analyses ORDER BY id")).all()
    assert first == second


def test_backfill_chunks_instead_of_loading_everything(db):
    """청크 크기가 선언돼 있고 전량 로드가 아니다 — 30 MB 를 한 번에 올리지 않는다."""
    mod = _module()
    assert isinstance(mod._CHUNK, int) and 0 < mod._CHUNK <= 5000, (  # pylint: disable=protected-access
        f"청크 크기가 비정상: {mod._CHUNK}"  # pylint: disable=protected-access
    )
    assert "LIMIT" in _REV.read_text(encoding="utf-8"), "백필이 LIMIT 없이 전량을 읽는다"
