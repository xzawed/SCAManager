"""Analysis ORM 모델 — 분석 이력(정적 분석 + AI 리뷰 점수) 저장."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from src.database import Base


# pylint: disable=too-few-public-methods
class Analysis(Base):
    """Push/PR 분석 이력 테이블 — commit_sha별 점수·등급·AI 리뷰 결과 저장."""

    __tablename__ = "analyses"
    __table_args__ = (UniqueConstraint("repo_id", "commit_sha", name="uq_analyses_repo_sha"),)

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    commit_sha = Column(String, nullable=False, index=True)
    commit_message = Column(String, nullable=True)
    pr_number = Column(Integer, nullable=True)
    score = Column(Integer, nullable=True)
    grade = Column(String(1), nullable=True)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repository = relationship("Repository", back_populates="analyses")
