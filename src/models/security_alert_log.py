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
    # 🔴 AI 분류 · 사용자 결정 열은 쓰는 코드가 없다(회고 원장 L05 P2-87) — 그 기능을 만들 때까지 비어 있다.
    #    열은 남긴다(지우면 또 스키마 변경). No code writes these yet; kept to avoid another schema change.
    ai_classification = Column(String, nullable=True)
    ai_confidence = Column(Float, nullable=True)  # 0.0~1.0
    ai_reason = Column(String, nullable=True)  # 1줄 사유
    user_decision = Column(String, nullable=True)
    # GitHub 쪽 상태 — 폴링이 끝까지 받은 열린 목록에 없으면 "closed"(해결 · 무시), 다시 나타나면 "open"(회고 원장 L05 P1-35).
    # The alert's state on GitHub: "closed" once a complete open-alert list no longer has it, "open" again if it reappears.
    github_state = Column(String, nullable=False, default="open", server_default="open")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    processed_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True,
    )
