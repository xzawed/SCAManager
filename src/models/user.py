from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from src.database import Base


class User(Base):
    __tablename__ = "users"

    id           = Column(Integer, primary_key=True, index=True)
    google_id    = Column(String, unique=True, nullable=False, index=True)
    email        = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    created_at   = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    repositories = relationship("Repository", back_populates="owner")
