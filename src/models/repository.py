"""Repository ORM 모델 — 등록된 GitHub 리포지토리 정보."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database import Base


# pylint: disable=too-few-public-methods
class Repository(Base):
    """GitHub 리포지토리 테이블 — Webhook 등록 정보 및 소유 User FK."""

    __tablename__ = "repositories"

    id             = Column(Integer, primary_key=True, index=True)
    full_name      = Column(String, unique=True, nullable=False, index=True)
    telegram_chat_id = Column(String, nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    webhook_secret = Column(String, nullable=True)
    webhook_id     = Column(Integer, nullable=True)

    analyses = relationship("Analysis", back_populates="repository")
    owner    = relationship("User", back_populates="repositories")
