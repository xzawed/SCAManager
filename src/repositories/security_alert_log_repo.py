"""SecurityAlertProcessLog Repository — alert audit log upsert + GitHub 쪽 상태(열림 · 닫힘) 대조.

Cycle 73 F1 — GitHub Code Scanning + Secret Scanning alert 처리 추적.
Cycle 73 F1 — track GitHub Security alerts; reconcile their open/closed state on GitHub (retro ledger L05).
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.repository import Repository
from src.models.security_alert_log import SecurityAlertProcessLog

# GitHub 쪽 상태 값 / the alert's state on GitHub
OPEN = "open"
CLOSED = "closed"


def _apply_owner_filter(query, user_id: int | None):
    """🔴 user_id 기반 repo 소유권 격리 (1차 앱 필터 — cross-tenant 노출 차단, U0).
    Apply repo-ownership isolation by user_id (app-level 1st layer — blocks cross-tenant exposure).

    user_id None → 미적용(admin/legacy). 명시 → repo 소유자 == user_id OR repo 소유자 NULL(legacy 호환).
    dashboard_service._apply_analysis_user_filter 와 동일 의미론. alert 의 user_id 컬럼은 쓰는 곳이 없어
    늘 NULL 이라 repo_id→Repository.user_id 로 격리한다.
    user_id None → no-op (admin/legacy). Otherwise repo owner == user_id OR owner NULL (legacy compat).
    Mirrors _apply_analysis_user_filter; the alert.user_id column is never written, so isolate via
    repo_id → Repository.user_id.
    """
    if user_id is None:
        return query
    return query.join(Repository, SecurityAlertProcessLog.repo_id == Repository.id).filter(
        (Repository.user_id == user_id) | (Repository.user_id.is_(None))
    )


def upsert_alert_log(
    db: Session,
    *,
    repo_id: int,
    alert_type: str,
    alert_number: int,
    severity: str | None = None,
    rule_id: str | None = None,
) -> SecurityAlertProcessLog:
    """(repo, alert_type, alert_number) 조합에 대한 audit log upsert — 폴링이 받은 «열린» alert 이다.

    Upsert the audit log per (repo, alert_type, alert_number) for an alert the poller saw open.
    기존 레코드는 심각도를 갱신하고 GitHub 상태를 "open" 으로 되돌린다(닫혔다가 다시 열린 alert).
    An existing row gets its severity refreshed and its GitHub state set back to open (a reopened alert).
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
        if severity is not None:
            existing.severity = severity
        existing.github_state = OPEN
        db.commit()
        db.refresh(existing)
        return existing

    log = SecurityAlertProcessLog(
        repo_id=repo_id,
        alert_type=alert_type,
        alert_number=alert_number,
        severity=severity,
        rule_id=rule_id,
        github_state=OPEN,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def close_missing_alerts(
    db: Session, *, repo_id: int, alert_type: str, open_numbers: set[int],
) -> int:
    """폴링이 **끝까지** 받은 열린 목록(`open_numbers`)에 없는 그 repo · 종류의 열린 행을 "closed" 로 — 닫은 수를 돌려준다.

    🔴 부분 목록으로 부르면 실제로 열린 alert 을 닫아 «신규 pending» 에서 숨긴다 — 호출자는 완전한 목록일 때만 부른다
    (`security_scan_service._record_alerts`). 회고 원장 L05 P1-35.
    Mark this repo/type's open rows that are absent from a COMPLETE open-alert list as closed; returns how many.
    Calling it with a partial list would hide alerts that are still open.
    """
    q = db.query(SecurityAlertProcessLog).filter(
        SecurityAlertProcessLog.repo_id == repo_id,
        SecurityAlertProcessLog.alert_type == alert_type,
        SecurityAlertProcessLog.github_state == OPEN,
    )
    if open_numbers:
        q = q.filter(SecurityAlertProcessLog.alert_number.notin_(sorted(open_numbers)))
    closed = q.update({SecurityAlertProcessLog.github_state: CLOSED}, synchronize_session=False)
    db.commit()
    return int(closed or 0)


def list_pending(
    db: Session, *, user_id: int | None = None, repo_id: int | None = None, limit: int = 50,
) -> list[SecurityAlertProcessLog]:
    """GitHub 에서 아직 열려 있는 alert 목록 (dashboard 진입 시 표시).

    List alerts still open on GitHub, for the dashboard.
    user_id 명시 시 repo 소유권으로 cross-tenant 격리 (U0).
    """
    q = db.query(SecurityAlertProcessLog).filter(
        SecurityAlertProcessLog.user_decision.is_(None),
        SecurityAlertProcessLog.github_state == OPEN,
    )
    q = _apply_owner_filter(q, user_id)
    if repo_id is not None:
        q = q.filter(SecurityAlertProcessLog.repo_id == repo_id)
    return q.order_by(SecurityAlertProcessLog.processed_at.desc()).limit(limit).all()


def count_alerts(
    db: Session,
    *,
    user_id: int | None = None,
    repo_id: int | None = None,
) -> dict[str, int]:
    """alert 카운트 — {"total": 누적, "pending": GitHub 에서 열림, "closed": GitHub 에서 닫힘}.

    Count alerts: cumulative total, still open on GitHub (pending), closed on GitHub.
    user_id 명시 시 repo 소유권으로 cross-tenant 격리 (U0).
    """
    q = db.query(SecurityAlertProcessLog)
    q = _apply_owner_filter(q, user_id)
    if repo_id is not None:
        q = q.filter(SecurityAlertProcessLog.repo_id == repo_id)
    rows = q.all()
    counts: dict[str, int] = {"total": len(rows), "pending": 0, "closed": 0}
    for row in rows:
        if row.github_state == CLOSED:
            counts["closed"] += 1
        elif row.user_decision is None:
            counts["pending"] += 1
    return counts
