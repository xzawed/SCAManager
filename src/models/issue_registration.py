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
    # SHA256 해시 — AI: suggestion_text[:500] / 정적: JSON[tool, category, message[:200], file]
    # SHA256 hash — AI: suggestion_text[:500] / static: JSON[tool, category, message[:200], file]
    issue_key = Column(String(64), nullable=False)
    github_issue_number = Column(Integer, nullable=False)
    # "open" | "closed" — TTL 5분 캐시로 GitHub API 동기화
    # "open" | "closed" — synced from GitHub API with 5-minute TTL cache
    github_issue_state = Column(String, nullable=False, default="open", server_default="open")
    github_issue_synced_at = Column(DateTime, nullable=True)
    # 🔴 마지막 동기화가 **실패**했으면 그 원인 클래스 이름, 성공했으면 None (#1504 R3).
    #    이전에는 실패를 `pass` 로 삼켜 「마지막으로 알던 상태」를 그대로 보여 줬는데,
    #    일시 오류(5xx·타임아웃)에는 그것이 맞고 **영구 오류**(`InvalidURL` 등)에는 틀리다 —
    #    UI 에는 낡은 open/closed 가 성공적으로 동기화된 것처럼 보였다.
    #    `github_issue_synced_at` 은 실패 시 갱신되지 않으므로 TTL 마다 재시도는 하지만,
    #    **사용자는 그 상태가 낡았다는 사실을 알 수 없었다.**
    # Why the last sync failed (exception class name), or None on success: keeping the last
    # known state is right for transient errors and wrong for permanent ones, and the UI
    # could not tell the two apart.
    sync_error = Column(String, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
