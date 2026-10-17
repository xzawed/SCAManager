"""🔴 `GET /` 가 평균 4개를 내려고 분석 result JSON 전량을 파싱했다.

🔴 The overview page parsed every analysis `result` blob just to compute four averages.

## 실측 (운영 DB, 2026-08-23)

    행 수                         5,157
    result 전송 실크기            30 MB   (`sum(octet_length(result::text))`)
      행당 평균                  6,051 B
      행당 최대                    219 kB
    신뢰도 판정에 실제 필요한 5경로  80 kB
    ────────────────────────────────────
    비율                          약 384배

`pg_column_size` 는 TOAST **압축 후** 값(7.3 MB)이라 전송량이 아니다 — 위는 실전송 기준.
증가는 월 1.5~1.9 MB 로 선형·무한이다(보존 정책이 이 경로에 없다).

## 왜 이 축이 「바이트」인가

SQL 문자열 모양(`analyses.result` 가 select 목록에 있는가)으로 재면 방언마다 다르고,
JSON 경로 접근이 `JSON_EXTRACT` / `#>` 로 달라 오탐·미탐이 둘 다 난다. 대신 엔진의
`json_deserializer` 를 감싸 **파이썬으로 넘어온 JSON 바이트를 직접 센다** — 그것이
비용 그 자체이고 방언에 무관하다.

## 같이 고정하는 것: 평균이 무엇을 세는가

첫 화면 평균은 검증 여부와 상관없이 **점수가 저장된 분석 전부**다(사용자 결정 2026-10-17).
신뢰 불가 사유 6종을 심어 두고 평균 자체를 단언한다 — 어느 사유든 평균에서 다시 빠지면
(예: `score_unreliable` 필터가 되살아나면) 값이 달라진다.

## 같이 고정하는 것: 카드 집계가 읽는 열

카드 집계는 `ix_analyses_repo_scores` 의 열만 읽어야 PostgreSQL 이 힙을 건너뛴다(0048).
"""
from __future__ import annotations

import re
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, literal, select
from sqlalchemy.orm import Session, aliased
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import visitors
from sqlalchemy.sql.schema import Column

from src.auth.session import CurrentUser, get_current_user
from src.database import Base
from src.main import app
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.scorer.reliability import score_is_unreliable
from src.ui.routes.overview import _repo_cards

# 행당 블롭 크기 — 운영 평균 6 kB 의 약 8배로 잡아 신호를 크게 만든다.
_FILLER = "x" * 50_000
_ROWS = 20

# 신뢰 불가 사유별 표본 — 하나라도 집계에 새면 평균이 달라진다.
_UNRELIABLE = (
    {"ai_review_status": "api_error"},
    {"ai_review_status": "disabled"},
    {"static_analysis_incomplete": True},
    {"source": "cli"},
    {"breakdown": {"ai_defaults_applied": True}},   # 🔴 truthy 판정 축
    {"static_uncovered_languages": ["rust"]},
)


@pytest.fixture(name="json_bytes")
def _engine_with_counter():
    """엔진 + 파싱된 JSON 바이트 카운터."""
    counter = {"bytes": 0}

    def counting_loads(s):
        counter["bytes"] += len(s)
        return json.loads(s)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        json_deserializer=counting_loads,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)

    user = User(id=1, github_id="1", github_login="o", email="o@x.com", display_name="O")
    repo = Repository(id=1, full_name="o/r", user_id=1)
    session.add_all([user, repo])
    session.flush()

    # 신뢰 가능한 행 — 점수 100 · 80. 아래 신뢰 불가 행(점수 1)도 첫 화면 평균에 전부 들어간다.
    reliable_scores = [100, 80]
    for i, score in enumerate(reliable_scores):
        result = {"ai_review_status": "success", "filler": _FILLER}
        session.add(Analysis(
            repo_id=1, commit_sha=f"ok{i:038d}", score=score, result=result,
            # 프로덕션 쓰기 경로와 **같은 방식**으로 캐시를 채운다 — 평균은 이 값과 무관하지만
            # 카드의 «미검증 포함» 표식이 이 캐시를 읽는다.
            score_unreliable=score_is_unreliable(result),
        ))
    for i in range(_ROWS):
        bad = dict(_UNRELIABLE[i % len(_UNRELIABLE)])
        bad["filler"] = _FILLER
        session.add(Analysis(
            repo_id=1, commit_sha=f"bad{i:037d}", score=1, result=bad,
            score_unreliable=score_is_unreliable(bad),
        ))
    session.commit()

    counter["bytes"] = 0  # 시드 비용은 세지 않는다 — 재는 것은 렌더 경로다

    class _Ctx:
        def __enter__(self):
            return session

        def __exit__(self, *_a):
            return False

    with (
        patch("src.ui.routes.overview.SessionLocal", return_value=_Ctx()),
        patch.object(app, "dependency_overrides", {
            get_current_user: lambda: CurrentUser(
                id=1, github_login="o", email="o@x.com",
                display_name="O", plaintext_token="t",
            ),
        }),
    ):
        yield counter, session

    session.close()
    engine.dispose()


def _render():
    resp = TestClient(app).get("/")
    assert resp.status_code == 200, resp.status_code
    return resp


def test_overview_does_not_parse_the_whole_result_blob(json_bytes):
    """🔴 렌더 한 번이 파싱하는 JSON 바이트에 상한을 둔다.

    시드된 블롭 총량은 22행 × 50 kB ≈ 1.1 MB 다. 신뢰도 판정에 필요한 것은 마커
    5개뿐이므로, 블롭을 통째로 읽지 않는다면 파싱량은 그 1/10 에도 한참 못 미친다.
    """
    counter, _ = json_bytes
    _render()
    # 0046 이후 이 화면은 `result` 를 **전혀** 읽지 않는다 — 평균은 SQL 이 낸다.
    # 상한을 시드의 1/1000 로 조인다(투영 시절엔 1/10 이었다). 0 으로 두지 않는 것은
    # 다른 카드가 소량의 JSON 을 읽을 여지를 남기기 위함이고, 블롭 로드는 이 값을
    # 세 자릿수로 넘긴다(실측: 수정 전 1,101,041 바이트).
    seeded = _ROWS * len(_FILLER)
    # 🔴 실측은 **정확히 0** 이다 — 주장과 단언을 일치시킨다(Grok `01a02f70` Q5-4:
    #    「0 이라 주장하고 '작다'로 단언하는 간극」). 다른 카드가 JSON 을 읽기 시작하면
    #    여기서 먼저 보이는 편이 낫다 — 느슨한 상한은 그 변화를 삼킨다.
    assert counter["bytes"] == 0, (
        f"렌더가 JSON {counter['bytes']:,} 바이트를 파싱했다 — 0 이어야 한다. "
        "평균은 SQL 이 내므로 이 화면은 result 를 읽지 않는다."
    )
    assert counter["bytes"] < seeded // 1000, (
        f"렌더가 JSON {counter['bytes']:,} 바이트를 파싱했다 (시드 블롭 {seeded:,}). "
        "평균 4개를 내려고 분석 result 를 읽고 있다 — SQL 집계가 아니다."
    )


# 렌더된 카드에서 **점수 자리**만 뽑는다. 페이지 전체를 문자열로 훑으면 CSS 가 걸린다.
# Extract the score from its own element; scanning the whole page hits CSS.
_SCORE_IN_CARD = re.compile(
    r'<span class="repo-card__score">(\d+)<span'
)


def _rendered_average() -> str | None:
    """카드에 실제로 그려진 평균 점수. 없으면 None."""
    match = _SCORE_IN_CARD.search(_render().text)
    return match.group(1) if match else None


def test_the_score_element_is_actually_present(json_bytes):
    """🔴 계기 자기검증 — 점수 자리를 못 찾으면 아래 단언이 공허하다.

    템플릿 구조가 바뀌면 정규식이 못 맞추고, 그때 `None == 기대 평균` 이 아니라
    **여기가 먼저** red 가 되어 원인을 가리킨다.
    """
    assert _rendered_average() is not None, (
        "`repo-card__score` 안의 점수를 못 찾았다 — 템플릿 구조가 바뀌었다면 "
        "`_SCORE_IN_CARD` 를 함께 고쳐야 한다"
    )


def test_a_bare_substring_scan_would_be_vacuous(json_bytes):
    """🔴 왜 부분문자열 스캔을 안 쓰는지 **실측으로** 고정한다 (감사 B4, #1519).

    이 테스트의 옛 판은 `assert "90" in body` 였다. 페이지에는 점수와 무관한 `90` 이
    여러 번 있어 **평균이 무엇이든 참**이었다 — 실측(이 픽스처):

        페이지 내 '90' 발생: 3
          ... 'rgba(180,190,254, 0.10)'      <- 색상값
          ... 'max-width: 900px; margin: 60p' <- 레이아웃
          ... 'max-width: 900px; margin: 48p'

    🔴 감사 보고는 `linear-gradient(90deg, …)` 를 원인으로 적었는데, **이 렌더 경로에는
    `90deg` 가 없다**(실측). 원인 문자열은 다르지만 결론은 같다 — 점수 자리 밖의 `90` 이
    존재하는 한 부분문자열 스캔은 공허하다.

    이 단언은 그 전제를 고정한다: 점수 자리 밖에도 `90` 이 있다.
    """
    body = _render().text
    score = _SCORE_IN_CARD.search(body)
    assert score is not None, "점수 자리를 못 찾았다 — 위 테스트가 먼저 red 여야 한다"
    outside = body[:score.start()] + body[score.end():]
    assert "90" in outside, (
        "점수 자리 밖에 `90` 이 없다 — 옛 부분문자열 방식이 우연히 작동하기 시작했다. "
        "이 파일의 서술이 낡았으니 다시 확인하라"
    )


def test_overview_average_counts_every_recorded_score(json_bytes):
    """🔴 첫 화면 평균 = 점수가 저장된 분석 전부 — 신뢰 불가 사유 6종도 전부 들어간다.

    신뢰 가능 100·80 과 신뢰 불가 점수 1 × 20 행 → (180 + 20) / 22 = 9.09 → 9.
    검증된 것만 모으던 옛 집계라면 90 이다.

    🔴 옛 판은 `assert "90" in body` 였고 **발화할 수 없었다** — CSS 의
    `linear-gradient(90deg, …)` 에 맞았다. 이제 카드의 점수 자리만 본다.
    """
    _, _sess = json_bytes
    recorded = [100, 80] + [1] * _ROWS
    want = str(round(sum(recorded) / len(recorded)))
    rendered = _rendered_average()
    assert rendered == want, (
        f"카드에 그려진 평균이 {rendered!r} 다 — 기록된 점수 {len(recorded)}개의 평균 {want} 이어야 "
        "한다. 신뢰 불가 행이 평균에서 빠졌다(검증된 것만이면 90)."
    )


# 카드 집계가 기대는 인덱스 — 모델(`src/models/analysis.py`)과 0048 이 같은 이름을 쓴다.
_SCORE_INDEX = "ix_analyses_repo_scores"


def _analyses_columns(stmt) -> set[str] | None:
    """`stmt` 가 참조하는 analyses 열 이름 — SQL 문자열이 아니라 **식 트리**에서 모은다.

    select 목록 · 집계 인자 · FILTER · WHERE · GROUP BY 어디서든, 별칭을 거쳐도 원래 열로 센다.
    analyses 를 아예 읽지 않는 문이면 None.
    Columns of `analyses` referenced anywhere in `stmt`, read from the expression tree.
    """
    table = Analysis.__table__
    touches = False
    found: set[str] = set()
    for node in visitors.iterate(stmt):
        if node is table or getattr(node, "element", None) is table:
            touches = True
        if isinstance(node, Column):
            base = table.c.get(node.name)
            if base is not None and node.shares_lineage(base):
                touches = True
                found.add(node.name)
    return found if touches else None


def _card_statements(session) -> list:
    """`_repo_cards` 가 실제로 실행하는 문 — ORM 실행 훅으로 모은다(쿼리를 여기 다시 쓰지 않는다)."""
    repos = session.query(Repository).all()
    seen: list = []

    def _collect(state):
        seen.append(state.statement)

    event.listen(session, "do_orm_execute", _collect)
    try:
        _repo_cards(session, repos)
    finally:
        event.remove(session, "do_orm_execute", _collect)
    return seen


def test_overview_card_aggregates_read_only_the_score_index_columns(json_bytes):
    """🔴 카드 집계는 `ix_analyses_repo_scores` 의 열만 읽는다 — 그래야 인덱스만으로 답한다.

    `count(analyses.id)` 하나만 섞여도 id 가 인덱스에 없어 Index Only Scan 이 막힌다 —
    PostgreSQL 17 은 NOT NULL 열의 count 를 count(*) 로 바꾸지 않는다. 운영(2026-10-17)에서
    이 집계는 그래서 힙 1,185페이지를 통째로 읽었다(`result` JSON 이 대부분 인라인이라 무겁다).
    SQLite 는 rowid 가 모든 인덱스에 들어 있어 이 차이를 계획으로 못 본다 — 그래서 식 트리에서 잰다.
    실제 계획은 `tests/integration/test_overview_reliable_avg_postgres.py` 가 PostgreSQL 에서 본다.
    """
    _, session = json_bytes
    index = next((ix for ix in Analysis.__table__.indexes if ix.name == _SCORE_INDEX), None)
    assert index is not None, f"모델에 {_SCORE_INDEX} 가 없다 — 카드 집계가 기댈 인덱스가 사라졌다"
    allowed = {c.name for c in index.columns}
    read = [cols for cols in map(_analyses_columns, _card_statements(session)) if cols is not None]
    # 분석 수 · 기록된 점수 평균 — 둘 다 analyses 를 읽는다. 못 잡으면 아래 단언이 공허하다.
    assert len(read) >= 2, f"analyses 를 읽는 카드 집계를 {len(read)}개만 잡았다 — 계기가 공허하다"
    outside = [sorted(cols - allowed) for cols in read if cols - allowed]
    assert not outside, (
        f"카드 집계가 {_SCORE_INDEX} 밖의 열을 읽는다: {outside} — 그 문은 힙을 읽는다. "
        "행 수는 count(Analysis.id) 가 아니라 func.count() 로 센다."
    )


def test_the_column_reader_catches_aliased_where_columns_and_ignores_literals():
    """🔴 계기 뒤집기 — `_analyses_columns` 가 «약속한 것» 과 «가장 싼 흉내» 를 가르는가.

    claimed(이름이 약속하는 것): 어느 절에 있든 · 별칭을 거쳐도 analyses 의 열이면 센다.
    cheap(첫 출력만 보고 떠올린 가장 싼 과정): 컴파일된 SQL 에서 `analyses.<열>` 을 정규식으로
    줍기, 또는 select 목록의 이름만 읽기.
    claimed 에만 있는 것 — 별칭(`analyses_1.`)으로 WHERE 에만 나오는 열 → 반드시 잡혀야 한다.
    cheap 에만 있는 것 — `'analyses.created_at'` 문자열을 `created_at` 라벨로 고른 것 → 반드시 무시돼야 한다.
    """
    other = aliased(Analysis)
    where_only = select(func.count()).select_from(other).where(other.created_at.isnot(None))
    literal_only = (select(Analysis.repo_id, literal("analyses.created_at").label("created_at"))
                    .group_by(Analysis.repo_id))
    assert _analyses_columns(where_only) == {"created_at"}
    assert _analyses_columns(literal_only) == {"repo_id"}
    assert _analyses_columns(select(Repository.id)) is None
