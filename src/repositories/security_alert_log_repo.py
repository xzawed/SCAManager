"""SecurityAlertProcessLog Repository — alert audit log upsert + 사용자 결정 갱신.

Cycle 73 F1 — GitHub Code Scanning + Secret Scanning alert 처리 추적.
Cycle 73 F1 — track GitHub Security alert processing.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.security_alert_log import SecurityAlertProcessLog


def upsert_alert_log(
    db: Session,
    *,
    repo_id: int,
    alert_type: str,
    alert_number: int,
    severity: str | None = None,
    rule_id: str | None = None,
    ai_classification: str | None = None,
    ai_confidence: float | None = None,
    ai_reason: str | None = None,
) -> SecurityAlertProcessLog:
    """(repo, alert_type, alert_number) 조합에 대한 audit log upsert.

    Upsert audit log per (repo, alert_type, alert_number).
    기존 레코드 있으면 AI 분류만 갱신 (user_decision 보존), 없으면 신규 INSERT.
    """
    existing = (
        db.query(SecurityAlertProcessLog)
        .filter(
            SecurityAlertProcessLog.repo_id == repo_id,
            SecurityAlertProcessLog.alert_type == alert_type,
            SecurityAlertProcessLog.alert_number == alert_number,
        )
        .first()
    )
    if existing is not None:
        if ai_classification is not None:
            existing.ai_classification = ai_classification
        if ai_confidence is not None:
            existing.ai_confidence = ai_confidence
        if ai_reason is not None:
            existing.ai_reason = ai_reason
        if severity is not None:
            existing.severity = severity
        db.commit()
        db.refresh(existing)
        return existing

    log = SecurityAlertProcessLog(
        repo_id=repo_id,
        alert_type=alert_type,
        alert_number=alert_number,
        severity=severity,
        rule_id=rule_id,
        ai_classification=ai_classification,
        ai_confidence=ai_confidence,
        ai_reason=ai_reason,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def record_user_decision(
    db: Session,
    *,
    log_id: int,
    user_id: int,
    decision: str,
) -> SecurityAlertProcessLog | None:
    """사용자 1-click confirm 결정 기록 (state 변경 = 정책 12 페어).

    Record user 1-click confirm decision (state change = policy 12 pair).
    decision = "accept_ai" | "override_dismiss" | "override_keep".
    """
    log = db.get(SecurityAlertProcessLog, log_id)
    if log is None:
        return None
    log.user_decision = decision
    log.user_id = user_id
    db.commit()
    db.refresh(log)
    return log


def list_pending(db: Session, *, repo_id: int | None = None, limit: int = 50) -> list[SecurityAlertProcessLog]:
    """user_decision IS NULL 인 pending alert 목록 (dashboard 진입 시 표시).

    List pending alerts (user_decision IS NULL) for dashboard display.
    """
    q = db.query(SecurityAlertProcessLog).filter(SecurityAlertProcessLog.user_decision.is_(None))
    if repo_id is not None:
        q = q.filter(SecurityAlertProcessLog.repo_id == repo_id)
    return q.order_by(SecurityAlertProcessLog.processed_at.desc()).limit(limit).all()


def count_by_classification(
    db: Session,
    *,
    repo_id: int | None = None,
) -> dict[str, int]:
    """분류별 alert 카운트 (dashboard baseline 측정 카드).

    Count alerts by classification (dashboard baseline measurement card).
    Returns: {classification: count, "total": N, "pending": M}.
    """
    q = db.query(SecurityAlertProcessLog)
    if repo_id is not None:
        q = q.filter(SecurityAlertProcessLog.repo_id == repo_id)
    rows = q.all()
    counts: dict[str, int] = {"total": len(rows), "pending": 0}
    for row in rows:
        if row.user_decision is None:
            counts["pending"] += 1
        key = row.ai_classification or "unclassified"
        counts[key] = counts.get(key, 0) + 1
    return counts
