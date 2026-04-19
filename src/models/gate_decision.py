"""GateDecision ORM 모델 — PR Gate 승인/반려 결정 이력."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from src.database import Base


# pylint: disable=too-few-public-methods
class GateDecision(Base):
    """PR Gate 승인·반려 결정 이력 테이블 (자동/반자동 모드 모두 기록)."""

    __tablename__ = "gate_decisions"
    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False, index=True)
    decision = Column(String, nullable=False)   # "approve" | "reject" | "skip"
    mode = Column(String, nullable=False)        # "auto" | "manual"
    decided_by = Column(String, nullable=True)
    decided_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
