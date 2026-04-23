"""AnalysisFeedback Repository — thumbs up/down upsert + 정합도 집계.

Phase E.3 — AI 점수 정합도 측정. (user, analysis) 조합당 1개 레코드 강제.
"""
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.analysis import Analysis
from src.models.analysis_feedback import AnalysisFeedback

# 점수 범위 정의 — grade 경계 기준 (F/D/C/B/A)
_SCORE_RANGES: tuple[tuple[str, int, int], ...] = (
    ("0-44", 0, 44),
    ("45-59", 45, 59),
    ("60-74", 60, 74),
    ("75-89", 75, 89),
    ("90-100", 90, 100),
)


def upsert_feedback(
    db: Session,
    *,
    analysis_id: int,
    user_id: int,
    thumbs: int,
    comment: str | None = None,
) -> AnalysisFeedback:
    """(analysis, user) 조합에 대한 피드백을 upsert.

    기존 레코드가 있으면 UPDATE (thumbs + comment), 없으면 INSERT.
    동일 사용자가 같은 분석을 여러 번 평가해도 레코드는 1개만 유지.

    Raises:
        ValueError: thumbs 가 +1 또는 -1 이 아닌 경우.
    """
    if thumbs not in (1, -1):
        raise ValueError(f"thumbs must be +1 or -1, got {thumbs}")

    existing = db.query(AnalysisFeedback).filter_by(
        analysis_id=analysis_id, user_id=user_id,
    ).first()

    if existing is not None:
        existing.thumbs = thumbs
        existing.comment = comment
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    fb = AnalysisFeedback(
        analysis_id=analysis_id,
        user_id=user_id,
        thumbs=thumbs,
        comment=comment,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def find_by_analysis_and_user(
    db: Session, *, analysis_id: int, user_id: int,
) -> AnalysisFeedback | None:
    """사용자의 기존 피드백 조회 (UI 상태 복원용)."""
    return db.query(AnalysisFeedback).filter_by(
        analysis_id=analysis_id, user_id=user_id,
    ).first()


def get_calibration_by_score_range(db: Session) -> dict[str, dict]:
    """점수 범위별 thumbs up 비율 집계 — Claude 점수 vs 사람 판단 정합도 지표.

    Returns:
        {
            "0-44":  {"count": N, "up_ratio": 0.0~1.0},
            "45-59": {...},
            "60-74": {...},
            "75-89": {...},
            "90-100": {...},
        }
        count 0 이면 up_ratio 는 0.0.
    """
    rows = (
        db.query(
            Analysis.score,
            AnalysisFeedback.thumbs,
            func.count(AnalysisFeedback.id),  # pylint: disable=not-callable
        )
        .join(AnalysisFeedback, AnalysisFeedback.analysis_id == Analysis.id)
        .group_by(Analysis.score, AnalysisFeedback.thumbs)
        .all()
    )

    result: dict[str, dict] = {}
    for range_name, lo, hi in _SCORE_RANGES:
        up_count = 0
        down_count = 0
        for score, thumbs, count in rows:
            if score is None or not lo <= score <= hi:
                continue
            if thumbs == 1:
                up_count += count
            elif thumbs == -1:
                down_count += count
        total = up_count + down_count
        result[range_name] = {
            "count": total,
            "up_ratio": (up_count / total) if total > 0 else 0.0,
        }
    return result
