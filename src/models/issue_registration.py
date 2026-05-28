"""IssueRegistration ORM — AI 분석 결과 GitHub Issue 등록 이력.
IssueRegistration ORM — records of GitHub Issues created from AI analysis results.
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from src.database import Base


# pylint: disable=too-few-public-methods
class IssueRegistration(Base):
    """분석 결과 항목별 GitHub Issue 등록 이력 — 중복 등록 방지 + 상태 동기화.
    Per-item GitHub Issue registration record — dedup guard + state sync.
    """

    __tablename__ = "issue_registrations"
    __table_args__ = (
        # 동일 리포 내 issue_key 중복 방지 — 리포 간 동일 이슈는 허용
        # Prevent duplicate issue_key within the same repo; allow same key across repos
        UniqueConstraint("repo_id", "issue_key", name="uq_issue_reg_repo_key"),
        Index("ix_issue_reg_analysis_id", "analysis_id"),
        Index("ix_issue_reg_repo_id", "repo_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer, ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False
    )
    repo_id = Column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    # "ai_suggestion" | "static_issue"
    issue_type = Column(String, nullable=False)
    # SHA256 해시 — AI: suggestion_text[:500] / 정적: tool:category:message[:200]
    # SHA256 hash — AI: suggestion_text[:500] / static: tool:category:message[:200]
    issue_key = Column(String(64), nullable=False)
    github_issue_number = Column(Integer, nullable=False)
    # "open" | "closed" — TTL 5분 캐시로 GitHub API 동기화
    # "open" | "closed" — synced from GitHub API with 5-minute TTL cache
    github_issue_state = Column(String, nullable=False, default="open", server_default="open")
    github_issue_synced_at = Column(DateTime, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
