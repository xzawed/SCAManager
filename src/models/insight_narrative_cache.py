"""InsightNarrativeCache ORM — Insight 모드 Claude AI narrative 1h TTL 캐시.

InsightNarrativeCache ORM — Insight mode Claude AI narrative 1h TTL cache.

0031 — `repo_id` nullable FK 추가 (repo_id=NULL: 전체 대시보드 캐시, repo_id=N: 리포별 캐시).
0031 — Add nullable `repo_id` FK (NULL=global dashboard cache, N=repo-specific cache).
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String

from src.database import Base


# pylint: disable=too-few-public-methods
class InsightNarrativeCache(Base):
    """Claude AI Insight narrative 응답 1h TTL 캐시.

    Claude AI Insight narrative response cache (1h TTL).
    """

    __tablename__ = "insight_narrative_cache"
    __table_args__ = (
        # 0031: old (user_id, days) UniqueConstraint removed — repo_id 추가로 다중 행 허용.
        # 0031: old (user_id, days) UniqueConstraint removed — multiple rows allowed with repo_id.
        # Partial uniqueness enforced by migration 0031 partial indexes (PG only).
        Index(
            "ix_insight_cache_user_days_language",
            "user_id", "days", "language",
        ),
        Index("ix_insight_cache_repo_id", "repo_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    days = Column(Integer, nullable=False)
    language = Column(String(5), nullable=False, default="en", server_default="en")
    # 0031 — repo-specific cache key (NULL = global dashboard narrative)
    # 0031 — 리포별 캐시 키 (NULL = 전체 대시보드 내러티브)
    repo_id = Column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    response_json = Column(JSON, nullable=False)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    expires_at = Column(DateTime, nullable=False, index=True)
