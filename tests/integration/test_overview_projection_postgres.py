"""🔴 신뢰도 경로 투영이 **PostgreSQL 에서도** 같은 판정을 내는가.

🔴 Whether the reliability-path projection yields the same verdict on PostgreSQL.

## 왜 SQLite 단위 테스트로는 못 잡나

`GET /` 는 `result` 블롭 전량 대신 `RELIABILITY_RESULT_PATHS` 5경로만 SQL 에서 투영한다
(실측 30 MB → 80 kB, 운영 DB 2026-08-23). 그런데 **JSON 값의 파이썬 타입이 백엔드마다
다르다** — SQLite 는 JSON 불린을 `0`/`1` 정수로 돌려주고(실측), PostgreSQL 은 그렇지 않다.
`score_is_unreliable` 은 `ai_defaults_applied is True` 로 **엄격 비교**하므로, 이 차이를
놓치면 그 행이 집계에서 안 빠지고 **평균이 조용히 틀어진다** — 예외도 red 도 없이.

단위 테스트는 두 표현을 *흉내내어* 고정한다(`tests/unit/scorer/test_reliability_projection.py`).
이 파일은 **진짜 psycopg2 가 무엇을 주는지** 잰다 — 흉내가 틀렸을 가능성이 그 축의 사각이다.

실행 조건 / Execution guard: `DATABASE_URL_TEST_POSTGRES` 설정 시에만 (pg-concurrency CI job).
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import Column, Integer, JSON, MetaData, Table, create_engine, select

from src.scorer.reliability import (
    RELIABILITY_RESULT_PATHS,
    result_from_projection,
    score_is_unreliable,
)

_PG_URL = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
_requires_postgres = pytest.mark.skipif(
    not _PG_URL, reason="투영 타입 검증은 PostgreSQL 필요 — DATABASE_URL_TEST_POSTGRES",
)

# 신뢰 불가 사유 6종 + 대조군. 각 사유가 **혼자서** 판정을 뒤집는지 본다.
_CORPUS = [
    {"ai_review_status": "success"},
    {"ai_review_status": "api_error"},
    {"ai_review_status": "parse_error"},
    {"ai_review_status": "disabled"},
    {"ai_review_status": "no_api_key"},
    {"ai_review_status": "empty_diff"},
    {"static_analysis_incomplete": True},
    {"static_analysis_incomplete": False},
    {"source": "cli"},
    {"source": "webhook"},
    {"breakdown": {"ai_defaults_applied": True}},    # 🔴 `is True` 엄격 비교 축
    {"breakdown": {"ai_defaults_applied": False}},
    {"static_uncovered_languages": ["rust"]},
    {"static_uncovered_languages": []},
    {},
    None,
]


@pytest.fixture(name="pg_table")
def _pg_table():
    """임시 테이블 하나 — 앱 스키마를 건드리지 않는다."""
    engine = create_engine(_PG_URL)
    meta = MetaData()
    table = Table(
        "tmp_projection_probe", meta,
        Column("id", Integer, primary_key=True),
        Column("result", JSON),
    )
    table.drop(engine, checkfirst=True)
    table.create(engine)
    try:
        yield engine, table
    finally:
        table.drop(engine, checkfirst=True)
        engine.dispose()


def _json_path(column, path):
    expr = column
    for key in path:
        expr = expr[key]
    return expr


@_requires_postgres
def test_projection_matches_full_blob_verdict_on_postgres(pg_table):
    """🔴 16 표본 전부에서 투영 판정 == 전체 blob 판정."""
    engine, table = pg_table
    with engine.begin() as conn:
        conn.execute(table.insert(), [
            {"id": i + 1, "result": r} for i, r in enumerate(_CORPUS)
        ])

    columns = [_json_path(table.c.result, p) for p in RELIABILITY_RESULT_PATHS]
    with engine.connect() as conn:
        rows = conn.execute(select(table.c.id, *columns).order_by(table.c.id)).all()

    assert len(rows) == len(_CORPUS), f"행 수 불일치: {len(rows)} != {len(_CORPUS)}"

    mismatches = []
    for row in rows:
        source = _CORPUS[row[0] - 1]
        expected = score_is_unreliable(source)
        got = score_is_unreliable(result_from_projection(list(row[1:])))
        if got != expected:
            mismatches.append((source, expected, got, list(row[1:])))

    assert not mismatches, (
        "PostgreSQL 투영이 다른 판정을 냈다 — 평균이 조용히 틀어진다:\n"
        + "\n".join(f"  입력={s} 전체={e} 투영={g} 투영값={v}" for s, e, g, v in mismatches)
    )


@_requires_postgres
def test_the_corpus_actually_exercises_both_verdicts(pg_table):
    """공허화 차단 — 표본이 한쪽으로 쏠리면 위 단언이 아무것도 못 본다."""
    verdicts = {score_is_unreliable(r) for r in _CORPUS}
    assert verdicts == {True, False}, f"표본이 한쪽뿐이다: {verdicts}"


@_requires_postgres
def test_postgres_json_boolean_python_type_is_recorded(pg_table):
    """🔴 계기 기록 — psycopg2 가 JSON 불린을 **무엇으로** 주는지 실측해 남긴다.

    이 값이 바뀌면(드라이버 업그레이드 등) `_json_bool` 정규화 표가 낡는다.
    가정이 아니라 실측으로 적어 둔다.
    """
    engine, table = pg_table
    with engine.begin() as conn:
        conn.execute(table.insert(), [
            {"id": 1, "result": {"breakdown": {"ai_defaults_applied": True}}},
        ])
    col = _json_path(table.c.result, ("breakdown", "ai_defaults_applied"))
    with engine.connect() as conn:
        value = conn.execute(select(col)).scalar()

    from src.scorer.reliability import _json_bool  # pylint: disable=import-outside-toplevel
    assert _json_bool(value) is True, (
        f"PostgreSQL 이 JSON true 를 {value!r}({type(value).__name__}) 로 주는데 "
        "_json_bool 이 True 로 정규화하지 못한다 — 정규화 표를 넓혀야 한다"
    )
