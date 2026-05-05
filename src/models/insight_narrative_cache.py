"""InsightNarrativeCache ORM — Insight 모드 Claude AI narrative 1h TTL 캐시.

Cycle 74 PR-B Phase 2-B 🅑 — UX 영향 최소 + 60% Anthropic API 비용 절감.
Cycle 74 PR-B Phase 2-B 🅑 — minimum UX impact + 60% Anthropic API cost reduction.

Phase 1 PR-1c (사이클 84) — 다국어 지원 캐시 키 분리:
- language 컬럼 추가 + composite index (user_id, days, language) 갱신
- 동일 사용자 다른 언어 transition 시 잘못된 캐시 hit 차단 (cross-verify 6차 §3.1 발견)

Phase 1 PR-1c (Cycle 84) — multilingual cache key separation:
- Add language column + composite index (user_id, days, language)
- Prevents stale cache hits when same user transitions languages
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from src.database import Base


# pylint: disable=too-few-public-methods
class InsightNarrativeCache(Base):
    """Claude AI Insight narrative 응답 1h TTL 캐시.

    Claude AI Insight narrative response cache (1h TTL).
    """

    __tablename__ = "insight_narrative_cache"
    __table_args__ = (
        UniqueConstraint("user_id", "days", name="uq_insight_cache_user_days"),
        # Phase 1 PR-1c — composite index (user_id, days, language) 캐시 키 분리
        # Phase 1 PR-1c — composite index for multilingual cache key separation
        Index(
            "ix_insight_cache_user_days_language",
            "user_id", "days", "language",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    days = Column(Integer, nullable=False)  # 윈도우 (1/7/30/90)
    # Phase 1 PR-1c — 다국어 캐시 키 (default "en", server_default 의존)
    # Phase 1 PR-1c — multilingual cache key (default "en", relies on server_default)
    language = Column(String(5), nullable=False, default="en", server_default="en")
    response_json = Column(JSON, nullable=False)
    # 4 카드 narrative + status + generated_at 통합 dict
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False,
    )
    expires_at = Column(DateTime, nullable=False, index=True)
