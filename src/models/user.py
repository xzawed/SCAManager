from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from src.database import Base


class User(Base):
    __tablename__ = "users"

    id                  = Column(Integer, primary_key=True, index=True)
    github_id           = Column(String, unique=True, nullable=False, index=True)
    github_login        = Column(String, nullable=True)
    github_access_token = Column(String, nullable=True)
    email               = Column(String, unique=True, nullable=False)
    display_name        = Column(String, nullable=False)
    created_at          = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repositories = relationship("Repository", back_populates="owner")
