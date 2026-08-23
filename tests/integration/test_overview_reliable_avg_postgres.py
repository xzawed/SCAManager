"""🔴 `GET /` 의 SQL 평균이 **파이썬 판정과 같은 값**을 내는가 — PostgreSQL 실측.

🔴 Whether the SQL average equals the Python-predicate average, measured on real PostgreSQL.

## 왜 이 파일이 PostgreSQL 전용인가

0046 이후 `GET /` 는 `result` 블롭을 읽지 않고 `AVG(score)` 를 SQL 에서 낸다.
신뢰 불가 행은 `Analysis.score_unreliable`(= `score_is_unreliable(result)` 의 캐시)로
SQL 에서 제외한다. 이 구조에서 틀릴 수 있는 것은 **성능이 아니라 값**이다:

  · 캐시가 판정과 어긋나면 평균이 조용히 달라진다
  · `AVG` 의 NULL 처리·반올림·Decimal 반환이 파이썬 평균과 갈릴 수 있다
  · 부분 인덱스 술어(`score IS NOT NULL AND score_unreliable IS NOT TRUE`)와
    쿼리 술어가 어긋나면 **결과는 같아도** Index Only Scan 을 놓친다

SQLite 는 `AVG` 의 수치 타입도 부분 인덱스 사용 여부도 PostgreSQL 과 다르다 —
그 축은 여기서만 관측된다.

실행 조건 / Execution guard: `DATABASE_URL_TEST_POSTGRES` 설정 시에만 (pg-concurrency CI job).
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from src.scorer.reliability import score_is_unreliable

_PG_URL = os.environ.get("DATABASE_URL_TEST_POSTGRES", "")
_requires_postgres = pytest.mark.skipif(
    not _PG_URL, reason="SQL 평균 동치 검증은 PostgreSQL 필요 — DATABASE_URL_TEST_POSTGRES",
)

# 점수와 신뢰도를 **교차**시킨다 — 한쪽 축만 있으면 필터가 절반만 검증된다.
_ROWS = [
    # (score, result)
    (100, {"ai_review_status": "success"}),                       # 신뢰 O
    (80, {"ai_review_status": "success", "breakdown": {}}),       # 신뢰 O
    (60, {"ai_review_status": "success"}),                        # 신뢰 O
    (10, {"ai_review_status": "api_error"}),                      # 신뢰 X
    (11, {"ai_review_status": "disabled"}),                       # 신뢰 X
    (12, {"static_analysis_incomplete": True}),                   # 신뢰 X
    (13, {"source": "cli"}),                                      # 신뢰 X
    (14, {"breakdown": {"ai_defaults_applied": True}}),           # 신뢰 X
    (15, {"static_uncovered_languages": ["rust"]}),               # 신뢰 X
    (None, {"ai_review_status": "success"}),                      # score NULL — 제외
]


@pytest.fixture(name="pg")
def _pg():
    """PG 세션 — 잔류 제거 후 clean slate (기존 PG 테스트 패턴)."""
    from src.database import Base  # pylint: disable=import-outside-toplevel
    from src.models.analysis import Analysis  # pylint: disable=import-outside-toplevel

    # 🔴 side-effect import 는 `# noqa: F401` 이 아니라 **튜플 참조**로 남긴다 —
    #    CodeQL 이 'used' 로 인식하고, import 가 사라지면 여기서 loud-fail 한다.
    #    (`import src.models.analysis` + `from ... import` 이중 형태도 게이트가 막는다.)
    _TABLE_REGISTRATION = (Analysis,)
    assert _TABLE_REGISTRATION, "모델이 Base.metadata 에 등록되지 않았다"

    engine = create_engine(_PG_URL, pool_pre_ping=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session, engine
    finally:
        session.close()
        engine.dispose()


def _seed(session):
    from src.models.analysis import Analysis  # pylint: disable=import-outside-toplevel
    from src.models.repository import Repository  # pylint: disable=import-outside-toplevel
    from src.models.user import User  # pylint: disable=import-outside-toplevel

    session.add(User(id=1, github_id="avg-pg", github_login="avg",
                     github_access_token="x", email="a@x.com", display_name="A"))
    session.add(Repository(id=1, full_name="o/r", user_id=1))
    session.flush()
    for i, (score, result) in enumerate(_ROWS):
        session.add(Analysis(
            repo_id=1, commit_sha=f"pgavg{i:035d}", score=score, result=result,
            # 프로덕션 쓰기 경로와 **같은 방식**으로 캐시를 채운다
            score_unreliable=score_is_unreliable(result),
        ))
    session.commit()


def _python_average() -> float:
    scores = [s for s, r in _ROWS if s is not None and not score_is_unreliable(r)]
    assert scores, "표본에 신뢰 가능한 점수가 없다 — 이 테스트가 공허하다"
    return sum(scores) / len(scores)


@_requires_postgres
def test_sql_average_equals_the_python_predicate_average(pg):
    """🔴 값 동치 — SQL 이 판정을 SQL 로 다시 쓴 것이 아니라 캐시를 쓰는지 확인한다."""
    from src.models.analysis import Analysis  # pylint: disable=import-outside-toplevel

    session, _ = pg
    _seed(session)

    got = (
        session.query(Analysis.repo_id, func.avg(Analysis.score))
        .filter(
            Analysis.repo_id.in_([1]),
            Analysis.score.isnot(None),
            Analysis.score_unreliable.isnot(True),
        )
        .group_by(Analysis.repo_id)
        .all()
    )
    assert len(got) == 1, f"그룹이 1개가 아니다: {got}"
    assert float(got[0][1]) == pytest.approx(_python_average()), (
        f"SQL 평균 {got[0][1]} != 파이썬 평균 {_python_average()} — "
        "캐시가 판정과 어긋났거나 필터가 다르다"
    )


@_requires_postgres
def test_the_sample_exercises_both_sides_of_the_filter(pg):
    """공허화 차단 — 신뢰 O/X 와 score NULL 이 모두 있어야 필터가 검증된다."""
    verdicts = {score_is_unreliable(r) for _, r in _ROWS}
    assert verdicts == {True, False}, f"신뢰도 축이 한쪽뿐: {verdicts}"
    assert any(s is None for s, _ in _ROWS), "score NULL 표본이 없다"


@_requires_postgres
def test_the_partial_index_is_actually_used(pg):
    """🔴 부분 인덱스가 실제로 쓰이는가 — 술어가 어긋나면 값은 맞고 성능만 조용히 죽는다.

    실측(로컬 PG17, 5,164행): 인덱스 사용 0.45 ms · 버퍼 6 / 미사용 2.17 ms · 버퍼 1,145.
    표본이 작아 계획이 Seq 로 갈 수 있으므로 **강제 후** 인덱스가 존재하고 쓰일 수 있는지 본다.
    """
    session, engine = pg
    _seed(session)
    with engine.connect() as conn:
        from sqlalchemy import text  # pylint: disable=import-outside-toplevel

        names = [r[0] for r in conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename='analyses'"))]
        assert "ix_analyses_reliable_scores" in names, (
            f"부분 인덱스가 생성되지 않았다: {names}"
        )
        conn.execute(text("SET LOCAL enable_seqscan = off"))
        plan = "\n".join(r[0] for r in conn.execute(text(
            "EXPLAIN SELECT repo_id, avg(score) FROM analyses"
            " WHERE score IS NOT NULL AND score_unreliable IS NOT TRUE"
            " GROUP BY repo_id")))
    assert "ix_analyses_reliable_scores" in plan, (
        "부분 인덱스를 쓸 수 없다 — 쿼리 술어가 인덱스 술어를 함의하지 않는다:\n" + plan
    )
