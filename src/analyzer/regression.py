"""Regression detection — 분석 점수가 직전 N건 평균 대비 급락하거나
F등급으로 진입했는지 판정하는 순수 함수.

Push 이벤트 워크플로우에서 품질 저하를 즉시 탐지하기 위해 사용된다.
반환 dict 형태:
    {"type": "drop"|"f_entry", "delta": float, "baseline": float}
두 조건이 동시 성립하면 type="drop"이 우선이며 secondary="f_entry"가 덧붙는다.
"""
from statistics import mean


def detect_regression(
    current_score: int,
    previous_scores: list[int],
    current_grade: str,
    drop_threshold: int,
) -> dict | None:
    """직전 점수 이력 대비 회귀를 감지한다.

    Args:
        current_score:      이번 분석 총점
        previous_scores:    직전 N건 점수 리스트 (비어있으면 감지 불가)
        current_grade:      이번 분석 등급 (F 여부 판정용)
        drop_threshold:     drop 감지 임계치 (baseline - current ≥ threshold → drop)

    Returns:
        회귀 감지 시 dict, 정상 시 None.
    """
    if not previous_scores:
        return None

    baseline = mean(previous_scores)
    delta = baseline - current_score

    is_drop = delta >= drop_threshold
    # F 진입: 현재 F 이고 직전 중 F가 아닌 점수(≥45)가 하나라도 있을 때
    is_f_entry = current_grade == "F" and any(s >= 45 for s in previous_scores)

    if is_drop:
        info = {"type": "drop", "delta": delta, "baseline": baseline}
        if is_f_entry:
            info["secondary"] = "f_entry"
        return info
    if is_f_entry:
        return {"type": "f_entry", "delta": delta, "baseline": baseline}
    return None
