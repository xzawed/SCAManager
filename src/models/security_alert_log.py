"""SecurityAlertProcessLog ORM — GitHub Code Scanning + Secret Scanning alert audit log.

Cycle 73 F1 — alert 별 분류 (Claude AI 권장 vs 사용자 결정) 추적.
Cycle 73 F1 — track classification (Claude AI suggestion vs user decision) per alert.

**CASCADE 삭제 의도**:
  - `repo_id ondelete=CASCADE`: 리포 삭제 시 관련 audit log 동반 삭제 (legacy 회귀 가드 페어)
  - `user_id ondelete=SET NULL`: 사용자 삭제 시 audit log 보존 (GDPR + 보안 감사 추적 의무)
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint

from src.database import Base


# pylint: disable=too-few-public-methods
class SecurityAlertProcessLog(Base):
    """GitHub Security alert (Code Scanning + Secret Scanning) 처리 audit log.

    GitHub Security alert (Code Scanning + Secret Scanning) processing audit log.
    """

    __tablename__ = "security_alert_process_logs"
    __table_args__ = (
        UniqueConstraint(
            "repo_id", "alert_type", "alert_number",
            name="uq_security_alert_process_logs",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(
        Integer, ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    alert_type = Column(String, nullable=False)  # "code_scanning" | "secret_scanning"
    alert_number = Column(Integer, nullable=False)  # GitHub alert # (per-repo unique)
    severity = Column(String, nullable=True)  # critical/high/medium/low/note
    rule_id = Column(String, nullable=True)  # CodeQL rule ID
    ai_classification = Column(String, nullable=True)
    # "false_positive" | "used_in_tests" | "actual_violation" | "deferred"
    ai_confidence = Column(Float, nullable=True)  # 0.0~1.0
    ai_reason = Column(String, nullable=True)  # 1줄 사유
    user_decision = Column(String, nullable=True)
    # NULL = pending / "accept_ai" / "override_dismiss" / "override_keep"
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processed_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True,
    )
