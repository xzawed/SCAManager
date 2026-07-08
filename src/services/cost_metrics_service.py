"""cost_metrics_service — 비용 집계 서비스 진입점(대시보드/운영이 소비). repo 위임.
cost_metrics_service — cost aggregation service entry point; delegates to the repo."""
from datetime import datetime

from sqlalchemy.orm import Session

from src.repositories import claude_api_cost_repo


def user_cost_summary(db: Session, *, user_id: int, days: int = 30, now: datetime | None = None) -> dict:
    """사용자 귀속 Anthropic 비용 요약 (dashboard KPI 용).
    User-attributed Anthropic cost summary (for the dashboard KPI)."""
    return claude_api_cost_repo.user_cost_summary(db, user_id=user_id, days=days, now=now)
