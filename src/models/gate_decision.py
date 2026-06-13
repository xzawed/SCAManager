"""GateDecision ORM 모델 — PR Gate 승인/반려 결정 이력."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from src.database import Base


# pylint: disable=too-few-public-methods
class GateDecision(Base):
    """PR Gate 승인·반려 결정 이력 테이블 (자동/반자동 모드 모두 기록)."""

    __tablename__ = "gate_decisions"
    id = Column(Integer, primary_key=True, index=True)
    # Phase H — Critical C7: ondelete=CASCADE 추가. Repository → Analysis →
    # GateDecision 삭제 사슬 일관성 보장. 미설정 시 Analysis 삭제 → FK violation.
    # `delete_repo_cascade` (ui/_helpers.py) 가 application-level 보완 중이지만,
    # 다른 경로 (admin script, future API) 에서 Analysis 삭제 시 안전망 필요.
    # MergeAttempt/MergeRetryQueue/AnalysisFeedback 은 이미 CASCADE — 일관성 확보.
    # P0-A: unique=True 추가 — gate_decision_repo.upsert() 는 분석 당 1건 upsert 이므로
    # UNIQUE constraint 필수. unique=True 는 자동으로 인덱스를 생성하므로 index=True 제거.
    # Phase H — Critical C7: add ondelete=CASCADE so direct Analysis deletion
    # propagates here too (mirrors MergeAttempt/MergeRetryQueue/AnalysisFeedback).
    # P0-A: unique=True enforces one gate_decision per analysis (upsert semantic).
    # unique=True implies an index, so index=True is dropped.
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    decision = Column(String, nullable=False)   # "approve" | "reject" | "skip"
    mode = Column(String, nullable=False)        # "auto" | "manual"
    decided_by = Column(String, nullable=True)
    decided_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
