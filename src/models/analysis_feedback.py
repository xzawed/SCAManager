"""AnalysisFeedback ORM — 분석 결과에 대한 사용자 thumbs up/down 피드백.

Phase E.3 — AI 점수 정합도 측정 기반. (user, analysis) 조합당 1개 레코드만 존재.
사용자가 재피드백 시 기존 레코드를 UPDATE (upsert 패턴 — repository 에서 처리).

**CASCADE 삭제 의도 (중요)**:
  - `analysis_id ondelete=CASCADE`: Analysis 삭제(리포 삭제) 시 관련 피드백 자동 삭제.
    정합도 지표는 현존 Analysis 기준이므로 고아 레코드 방지가 우선.
  - `user_id ondelete=CASCADE`: 사용자 계정 삭제 시 피드백 동반 삭제.
    **현재 계정 삭제 기능이 없어 실제 삭제는 발생하지 않으나**, 추후 GDPR 대비
    사용자 삭제 기능 추가 시 피드백 손실을 동반함을 인지할 것. 감사 추적이
    중요해지면 `SET NULL` + 익명화 전환 검토.
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
