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

from src.gate._common import ai_review_failed

# AI 미수행·기본값 적용 상태 — 점수 컬럼은 유지하되 검증 평균에서 제외.
# AI skipped / default-applied statuses — keep the score column, exclude from verified averages.
_AI_UNVERIFIED_STATUSES = frozenset({
    "disabled",
    "no_api_key",
    "empty_diff",
})


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
    # 🔴 `is True` 가 아니라 truthy 다 (2026-08-24).
    #    `is True` 는 불린이 아닌 참값(숫자 1·문자열)을 **신뢰 가능**으로 흘려보낸다 —
    #    기본값이 적용됐는데 집계에 남는 fail-open 이다. truthy 는 fail-closed 다.
    #    운영 실측: `ai_defaults_applied` 는 boolean 3,599행 + 키 없음 1,564행,
    #    **비-불린 0행** — 현재 데이터에서 이 변경은 증명 가능한 no-op 이다.
    #    Truthy, not `is True`: a non-boolean truthy marker must not slip through as reliable.
    #    Measured: 0 non-boolean values in production, so this is a provable no-op today.
    if isinstance(breakdown, dict) and breakdown.get("ai_defaults_applied"):
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
