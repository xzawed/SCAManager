"""RepoConfig ORM 모델 — 리포별 분석·Gate·알림 설정."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from src.database import Base


# pylint: disable=too-few-public-methods
class RepoConfig(Base):
    """리포별 Gate·알림 설정 테이블 (approve_mode·auto_merge·채널 설정 포함)."""

    __tablename__ = "repo_configs"
    id = Column(Integer, primary_key=True, index=True)
    repo_full_name = Column(String, unique=True, nullable=False, index=True)
    pr_review_comment = Column(Boolean, default=True, nullable=False)
    approve_mode = Column(String, default="disabled", nullable=False)
    approve_threshold = Column(Integer, default=75, nullable=False)
    reject_threshold = Column(Integer, default=50, nullable=False)
    notify_chat_id = Column(String, nullable=True)
    n8n_webhook_url = Column(String, nullable=True)
    discord_webhook_url = Column(String, nullable=True)
    slack_webhook_url = Column(String, nullable=True)
    custom_webhook_url = Column(String, nullable=True)
    email_recipients = Column(String, nullable=True)
    auto_merge = Column(Boolean, default=False, nullable=False)
    merge_threshold = Column(Integer, default=75, nullable=False)
    commit_comment = Column(Boolean, default=False, nullable=False)
    create_issue = Column(Boolean, default=False, nullable=False)
    hook_token = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __init__(self, **kwargs):
        kwargs.setdefault("pr_review_comment", True)
        kwargs.setdefault("approve_mode", "disabled")
        kwargs.setdefault("approve_threshold", 75)
        kwargs.setdefault("reject_threshold", 50)
        kwargs.setdefault("auto_merge", False)
        kwargs.setdefault("merge_threshold", 75)
        kwargs.setdefault("commit_comment", False)
        kwargs.setdefault("create_issue", False)
        super().__init__(**kwargs)
