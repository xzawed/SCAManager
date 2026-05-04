"""InsightNarrativeCache ORM — Insight 모드 Claude AI narrative 1h TTL 캐시.

Cycle 74 PR-B Phase 2-B 🅑 — UX 영향 최소 + 60% Anthropic API 비용 절감.
Cycle 74 PR-B Phase 2-B 🅑 — minimum UX impact + 60% Anthropic API cost reduction.

Key = (user_id, days) — 사용자별 + 윈도우별 격리.
TTL 만료만 무효화 (자동 invalidate 미적용 — MVP 단순화 default).
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, UniqueConstraint

from src.database import Base


# pylint: disable=too-few-public-methods
class InsightNarrativeCache(Base):
    """Claude AI Insight narrative 응답 1h TTL 캐시.

    Claude AI Insight narrative response cache (1h TTL).
    """

    __tablename__ = "insight_narrative_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "days", name="uq_insight_cache_user_days"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    days = Column(Integer, nullable=False)  # 윈도우 (1/7/30/90)
    response_json = Column(JSON, nullable=False)
    # 4 카드 narrative + status + generated_at 통합 dict
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    expires_at = Column(DateTime, nullable=False, index=True)
