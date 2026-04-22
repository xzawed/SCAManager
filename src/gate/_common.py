"""Gate 공용 헬퍼 — engine.py 와 actions/ 양쪽에서 공유."""
from __future__ import annotations

from src.scorer.calculator import ScoreResult


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
