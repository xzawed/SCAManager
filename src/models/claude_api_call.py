"""ClaudeApiCall ORM — Anthropic API 호출 비용 메트릭 영속화 (관측성·비용 대시보드).
ClaudeApiCall ORM — persists Anthropic API call cost metrics (observability, cost dashboard).

0043 — 신규 테이블 + RLS(user_id/repo_id 귀속). log_claude_api_call 이 매 호출 1행 INSERT(fail-safe).
0043 — New table + RLS. log_claude_api_call inserts one row per call (fail-safe).
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String

from src.database import Base


# pylint: disable=too-few-public-methods
class ClaudeApiCall(Base):
    """Anthropic API 호출 1건의 비용/토큰/귀속 메트릭.
    One Anthropic API call's cost/token/attribution metrics."""

    __tablename__ = "claude_api_calls"
    __table_args__ = (
        Index("ix_claude_api_calls_created_at", "created_at"),
        Index("ix_claude_api_calls_user_created", "user_id", "created_at"),
        Index("ix_claude_api_calls_repo_created", "repo_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    model = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="success")  # success/error/timeout
    input_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    output_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    cache_read_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    cache_creation_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    cost_usd = Column(Float, nullable=False, default=0.0, server_default="0")
    duration_ms = Column(Float, nullable=False, default=0.0, server_default="0")
    # 귀속 — 리뷰 경로=repo_id, 인사이트 경로=user_id (둘 다 nullable, CASCADE)
    # Attribution — review path=repo_id, insight path=user_id (both nullable, CASCADE)
    repo_id = Column(Integer, ForeignKey("repositories.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    error_type = Column(String(64), nullable=True)
