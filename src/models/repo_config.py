from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from src.database import Base


class RepoConfig(Base):
    __tablename__ = "repo_configs"
    id = Column(Integer, primary_key=True, index=True)
    repo_full_name = Column(String, unique=True, nullable=False, index=True)
    gate_mode = Column(String, default="disabled", nullable=False)
    auto_approve_threshold = Column(Integer, default=75, nullable=False)
    auto_reject_threshold = Column(Integer, default=50, nullable=False)
    notify_chat_id = Column(String, nullable=True)
    n8n_webhook_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __init__(self, **kwargs):
        kwargs.setdefault("gate_mode", "disabled")
        kwargs.setdefault("auto_approve_threshold", 75)
        kwargs.setdefault("auto_reject_threshold", 50)
        super().__init__(**kwargs)
