"""AnalysisFeedback ORM — 분석 결과에 대한 사용자 thumbs up/down 피드백.

Phase E.3 — AI 점수 정합도 측정 기반. (user, analysis) 조합당 1개 레코드만 존재.
사용자가 재피드백 시 기존 레코드를 UPDATE (upsert 패턴 — repository 에서 처리).
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from src.database import Base


# pylint: disable=too-few-public-methods
class AnalysisFeedback(Base):
    """분석 결과에 대한 사용자 피드백 — thumbs up (+1) / thumbs down (-1)."""

    __tablename__ = "analysis_feedbacks"
    __table_args__ = (
        UniqueConstraint("analysis_id", "user_id", name="uq_feedback_analysis_user"),
    )

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    thumbs = Column(Integer, nullable=False)  # +1 (up) | -1 (down)
    comment = Column(String, nullable=True)  # optional 자유 코멘트
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
