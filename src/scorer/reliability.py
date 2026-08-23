"""점수 신뢰도 분류 — 집계 오염 방지와 상세 페이지 표시를 분리한다.
Score reliability classification — keep detail scores while excluding unverified ones from averages.

R46 선택 (flag, not NULL for new categories):
- NULL-persist 는 genuine AI 실패(`api_error`/`parse_error`)만 — 기존 계약 유지.
- CLI / AI 기본값 / disabled / uncovered 는 **점수를 저장하되** 집계에서 제외.
  이유: 역사 행 rewrite 금지 + 상세 페이지가 점수·breakdown 을 보여줘야 함.
  집계는 `score_is_unreliable(result)` 로 result 마커를 읽어 필터 (마이그레이션 0).

R46 choice (flag, not NULL for new categories):
- NULL-persist stays limited to genuine AI failures (existing contract).
- CLI / AI-defaults / disabled / uncovered **persist the score** but aggregates exclude them.
  Historical rows are not rewritten; the detail page keeps score/breakdown visible.
  Aggregates filter via `score_is_unreliable(result)` markers (zero migrations).
"""
from __future__ import annotations

from collections.abc import Sequence

from src.gate._common import ai_review_failed

# AI 미수행·기본값 적용 상태 — 점수 컬럼은 유지하되 검증 평균에서 제외.
# AI skipped / default-applied statuses — keep the score column, exclude from verified averages.
_AI_UNVERIFIED_STATUSES = frozenset({
    "disabled",
    "no_api_key",
    "empty_diff",
})


# 🔴 `score_is_unreliable` 이 읽는 result 경로 — **단일 출처**.
#
# 집계 경로(`GET /`)는 평균을 내려고 result 블롭을 통째로 파싱했다. 실측(운영 DB
# 2026-08-23): 5,157행 · 전송 30 MB · 그중 판정에 쓰이는 것은 80 kB(약 384배).
# 아래 경로만 SQL 에서 투영하면 같은 판정을 같은 값으로 내면서 블롭을 읽지 않는다.
#
# 🔴 이 튜플이 낡으면 **판정이 조용히 틀린다** — 새 마커를 `score_is_unreliable` 에
#    추가하고 여기 안 넣으면 투영 경로에서 그 마커가 늘 None 이라 걸리지 않는다.
#    `tests/unit/scorer/test_reliability_projection.py` 가 함수 본문을 AST 로 읽어
#    실제로 접근하는 키와 이 선언을 대조한다.
# Single source for the result paths the predicate reads, so the aggregate path can project
# them instead of parsing the whole blob. A stale tuple silently breaks the verdict; an AST
# guard compares this against the keys the function actually touches.
RELIABILITY_RESULT_PATHS: tuple[tuple[str, ...], ...] = (
    ("ai_review_status",),
    ("static_analysis_incomplete",),
    ("source",),
    ("breakdown", "ai_defaults_applied"),
    ("static_uncovered_languages",),
)


def _json_bool(value: object) -> object:
    """JSON 불린 정규화 — 백엔드마다 타입이 다르다.

    🔴 SQLite 는 JSON 불린을 **0/1 정수**로 돌려준다(실측). `score_is_unreliable` 은
    `ai_defaults_applied is True` 로 **엄격 비교**하므로 `1 is True` 는 False 다 —
    정규화하지 않으면 그 행이 집계에서 안 빠지고 평균이 조용히 틀어진다.
    PostgreSQL 은 True/False 로 준다. 둘을 여기서 하나로 만든다.
    SQLite returns JSON booleans as 0/1; the predicate uses `is True`, so normalize.
    """
    if value is None or isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value


def result_from_projection(values: "Sequence[object]") -> dict:
    """`RELIABILITY_RESULT_PATHS` 순서의 투영값 → 판정이 읽는 최소 dict.

    반환값은 `score_is_unreliable` 에 **그대로** 넣을 수 있다 — 판정 로직은 하나뿐이고
    이 함수는 입력 모양만 복원한다(로직을 두 벌로 만들지 않는 것이 요점).
    Rebuilds the minimal dict the predicate reads; the predicate itself is never duplicated.
    """
    if len(values) != len(RELIABILITY_RESULT_PATHS):
        raise ValueError(
            f"투영값 {len(values)}개 != 선언된 경로 {len(RELIABILITY_RESULT_PATHS)}개"
        )
    out: dict = {}
    for path, value in zip(RELIABILITY_RESULT_PATHS, values):
        if value is None:
            continue
        node = out
        for key in path[:-1]:
            node = node.setdefault(key, {})
        node[path[-1]] = _json_bool(value)
    return out


def score_is_unreliable(result: dict | None) -> bool:
    """집계(평균·리더보드)에서 제외해야 하는 점수면 True.
    True when this analysis must not enter verified score averages.

    판정은 result dict 마커만 본다 — Analysis.score 컬럼 NULL 여부와 독립.
    Reads only result-dict markers — independent of whether Analysis.score is NULL.
    """
    if not result:
        return False
    if ai_review_failed(result):
        return True
    if result.get("static_analysis_incomplete"):
        return True
    if result.get("source") == "cli":
        return True
    status = result.get("ai_review_status")
    if status in _AI_UNVERIFIED_STATUSES:
        return True
    breakdown = result.get("breakdown")
    if isinstance(breakdown, dict) and breakdown.get("ai_defaults_applied") is True:
        return True
    uncovered = result.get("static_uncovered_languages") or []
    if uncovered:
        return True
    return False


def should_null_persist_score(result: dict | None) -> bool:
    """score/grade 컬럼을 NULL 로 저장해야 하면 True (genuine AI 실패만).
    True when score/grade columns must be NULL-persisted (genuine AI failure only).

    그 외 신뢰 불가 사유는 점수를 남기고 `score_is_unreliable` 로 집계만 제외한다.
    Other unreliable reasons keep the score and only filter aggregates.
    """
    if not result:
        return False
    return ai_review_failed(result)
