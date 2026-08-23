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

## 같이 고정하는 것: 의미가 안 바뀌었는가

투영으로 바꾸면 신뢰도 판정 입력이 달라진다. SQLite 는 JSON 불린을 **0/1 정수**로 주는데
`score_is_unreliable` 은 `ai_defaults_applied is True` 로 **엄격 비교**한다
(`src/scorer/reliability.py`) — 정규화를 빠뜨리면 그 행이 집계에서 안 빠지고 평균이
조용히 틀어진다. 그래서 평균 자체를 함께 단언한다.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from src.auth.session import CurrentUser, get_current_user
from src.database import Base
from src.main import app
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.models.user import User
from src.scorer.reliability import score_is_unreliable

# 행당 블롭 크기 — 운영 평균 6 kB 의 약 8배로 잡아 신호를 크게 만든다.
_FILLER = "x" * 50_000
_ROWS = 20

# 신뢰 불가 사유별 표본 — 하나라도 집계에 새면 평균이 달라진다.
_UNRELIABLE = (
    {"ai_review_status": "api_error"},
    {"ai_review_status": "disabled"},
    {"static_analysis_incomplete": True},
    {"source": "cli"},
    {"breakdown": {"ai_defaults_applied": True}},   # 🔴 `is True` 엄격 비교 축
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

    # 신뢰 가능한 행 — 점수 100 · 80 (평균 90). 나머지는 전부 제외돼야 한다.
    reliable_scores = [100, 80]
    for i, score in enumerate(reliable_scores):
        result = {"ai_review_status": "success", "filler": _FILLER}
        session.add(Analysis(
            repo_id=1, commit_sha=f"ok{i:038d}", score=score, result=result,
            # 🔴 프로덕션 쓰기 경로와 **같은 방식**으로 캐시를 채운다. 여기서 빠뜨리면
            #    server_default(false) 가 들어가 신뢰 불가 행이 평균에 섞인다 —
            #    즉 이 한 줄이 곧 프로덕션의 실패 모드다.
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
    assert counter["bytes"] < seeded // 1000, (
        f"렌더가 JSON {counter['bytes']:,} 바이트를 파싱했다 (시드 블롭 {seeded:,}). "
        "평균 4개를 내려고 분석 result 를 읽고 있다 — SQL 집계가 아니다."
    )


def test_overview_average_excludes_every_unreliable_reason(json_bytes):
    """🔴 의미 비회귀 — 투영이 신뢰도 판정을 바꾸면 평균이 조용히 틀어진다.

    특히 `ai_defaults_applied` 는 `is True` 엄격 비교라, SQLite 가 주는 0/1 정수를
    정규화하지 않으면 이 행이 집계에 남아 평균이 90 이 아니게 된다.
    """
    _, _sess = json_bytes
    body = _render().text
    assert "90" in body, (
        "평균이 90 이 아니다 — 신뢰 불가 행이 집계에 섞였다. "
        f"신뢰 가능 행은 100·80 둘뿐이고 나머지 {_ROWS} 행은 전부 제외돼야 한다."
    )
