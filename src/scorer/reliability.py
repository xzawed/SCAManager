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


# 🔴 판정이 `is True` 로 **엄격 비교**하는 경로 — 여기만 불린 정규화 대상이다.
#
# Grok claim-review `01a02f14` Q1 적발: 초판은 정규화를 **전 경로**에 걸었고, 그것이
# 오히려 발산을 만들었다. 실측 반례:
#   `{"static_analysis_incomplete": "false"}` → 전체: 비어있지 않은 문자열이라 truthy → True
#                                              투영: "false" → False 로 뒤집힘
#   `{"static_uncovered_languages": "false"}` → 같은 형태
# 그 두 경로는 **truthy 판정**이라 SQLite 의 0/1 이 그대로 들어가도 결과가 같다.
# 정규화가 필요한 것은 `is True` 하나뿐이다 — 좁히면 위 반례가 사라진다.
# Normalizing every path created divergences; only the strict-identity path needs it.
_STRICT_BOOL_PATHS: frozenset[tuple[str, ...]] = frozenset({
    ("breakdown", "ai_defaults_applied"),
})


def _json_bool(value: object) -> object:
    """SQLite 의 JSON 불린(0/1 정수)을 파이썬 불린으로 되돌린다.

    🔴 **정수 0/1 만** 건드린다. 문자열 `"true"`/`"false"` 는 손대지 않는다 —
    전체 blob 경로에서 `"true" is True` 는 False 이므로, 여기서 True 로 바꾸면
    없던 발산이 생긴다(초판이 그랬다).

    🔴 남는 한계(실측·정직 기준): SQLite 에서 JSON `true` 와 JSON `1` 은 추출 후
    **구별 불가능**하다. 저장값이 숫자 `1` 이면 전체 blob 은 `1 is True`=False,
    투영은 True 가 된다. PostgreSQL(운영)은 둘을 구별하므로 이 발산이 없고,
    현재 기록자는 항상 불린을 저장한다(`scorer/calculator.py` · `worker/pipeline.py`).
    이 한계는 테스트가 명시적으로 고정한다 — 모르고 지나가지 않는다.
    Only int 0/1 is converted; strings are left alone. On SQLite a stored numeric 1 is
    indistinguishable from JSON true after extraction (documented and pinned by a test).
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
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
        # 엄격 비교 경로만 정규화한다 — truthy 판정 경로는 원값 그대로가 동치다.
        node[path[-1]] = _json_bool(value) if path in _STRICT_BOOL_PATHS else value
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
