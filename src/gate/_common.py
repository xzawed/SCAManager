"""Gate 공용 헬퍼 — engine.py 와 actions/ 양쪽에서 공유."""
from __future__ import annotations

from src.scorer.calculator import ScoreResult

# AI 리뷰가 실제로 실패(API 호출/JSON 파싱 오류)한 상태 — auto-merge/auto-approve 차단 대상.
# 정상(success)·의도적 미수행(no_api_key/empty_diff/disabled)은 제외하여 기존 동작을 보존한다
# (AI 미사용 리포가 영구히 자동 머지 불가가 되는 회귀 방지).
# AI review statuses that mean a genuine failure (API/parse error) — block auto actions.
# success and intentional skips (no_api_key/empty_diff/disabled) are excluded to preserve behavior
# (so AI-disabled repos are not permanently blocked from auto-merge).
AI_REVIEW_FAILED_STATUSES = frozenset({"api_error", "parse_error"})


def ai_review_failed(result: dict) -> bool:
    """result_dict 의 ai_review_status 가 genuine 실패면 True (auto 차단 판정).

    static_analysis_incomplete 와 대칭 — AI 리뷰가 실제 실패했는데 중립-고점 기본값(44점)이
    적용되면 점수가 인플레이션되어 미검증 코드가 auto-merge/auto-approve 될 수 있다(fail-open).
    키 부재(구 레코드)·정상·의도적 미수행은 False 로 차단하지 않는다.
    Return True when ai_review_status is a genuine failure — symmetric with
    static_analysis_incomplete. Missing key, success, and intentional skips return False.
    """
    return result.get("ai_review_status") in AI_REVIEW_FAILED_STATUSES


def score_from_result(result: dict) -> ScoreResult:
    """result dict 에서 최소한의 ScoreResult 를 재구성한다.

    engine.py 의 Telegram semi-auto 경로 + actions/approve.py 양쪽에서
    사용. 단일 출처 보장으로 로직 드리프트 방지.
    """
    bd = result.get("breakdown") or {}
    return ScoreResult(
        total=result.get("score", 0),
        grade=result.get("grade", "F"),
        code_quality_score=bd.get("code_quality", 0),
        security_score=bd.get("security", 0),
        breakdown=bd,
    )
