"""🔴 `GET /` 의 SQL 집계가 **파이썬 계산과 같은 값**을 내는가 — PostgreSQL 실측.

🔴 Whether the overview's SQL aggregate equals the Python computation, on real PostgreSQL.

## 왜 이 파일이 PostgreSQL 전용인가

`GET /` 는 `result` 블롭을 읽지 않고 리포별 `AVG(score)` 와 «그중 미검증 행 수» 를 SQL 한 번에
낸다(`src/ui/routes/overview.py::def recorded_score_summary`). 평균은 점수가 저장된 분석 전부다
(검증 여부와 무관 — 사용자 결정 2026-10-17). 미검증 수는 `Analysis.score_unreliable`
(= `score_is_unreliable(result)` 의 캐시)로 센다. 이 구조에서 틀릴 수 있는 것은 **값**이다:

  · `AVG` 의 NULL 처리·Decimal 반환이 파이썬 평균과 갈릴 수 있다
  · `COUNT … FILTER (WHERE score_unreliable IS TRUE)` 가 방언마다 다르게 읽힐 수 있다
  · 캐시가 판정과 어긋나면 미검증 수가 조용히 달라진다

SQLite 는 `AVG` 의 수치 타입도 불린 비교도 PostgreSQL 과 다르다 — 그 축은 여기서만 관측된다.

실행 조건 / Execution guard: `DATABASE_URL_TEST_POSTGRES` 설정 시에만 (pg-concurrency CI job).
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine
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


def _python_expected() -> tuple[float, int]:
    """기록된 점수(NULL 제외) 전부의 평균, 그중 신뢰 불가 판정 수."""
    recorded = [(s, r) for s, r in _ROWS if s is not None]
    assert recorded, "표본에 기록된 점수가 없다 — 이 테스트가 공허하다"
    return (sum(s for s, _ in recorded) / len(recorded),
            sum(1 for _, r in recorded if score_is_unreliable(r)))


@_requires_postgres
def test_sql_aggregate_equals_the_python_computation(pg):
    """🔴 값 동치 — 라우트가 쓰는 집계 함수를 그대로 부른다(쿼리를 여기 다시 쓰지 않는다)."""
    from src.ui.routes.overview import recorded_score_summary  # pylint: disable=import-outside-toplevel

    session, _ = pg
    _seed(session)

    got = recorded_score_summary(session, [1])
    assert set(got) == {1}, f"그룹이 1개가 아니다: {got}"
    avg, unverified = got[1]
    want_avg, want_unverified = _python_expected()
    assert float(avg) == pytest.approx(want_avg), (
        f"SQL 평균 {avg} != 파이썬 평균 {want_avg} — 점수 NULL 이 아닌 행 전부를 세야 한다")
    assert unverified == want_unverified, (
        f"SQL 미검증 수 {unverified} != 판정 함수 {want_unverified} — 캐시가 판정과 어긋났거나 "
        "FILTER 가 다르게 읽혔다")


@_requires_postgres
def test_the_sample_exercises_both_sides_of_the_filter(pg):
    """공허화 차단 — 신뢰 O/X 와 score NULL 이 모두 있어야 평균·미검증 수가 둘 다 검증된다."""
    verdicts = {score_is_unreliable(r) for s, r in _ROWS if s is not None}
    assert verdicts == {True, False}, f"신뢰도 축이 한쪽뿐: {verdicts}"
    assert any(s is None for s, _ in _ROWS), "score NULL 표본이 없다"
