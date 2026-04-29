"""merge_attempt_repo — MergeAttempt 영속화 + 집계 쿼리 단일 출처.

Phase F.1 관측 기반. Phase 3 PR-B1 에서 lifecycle 전이 함수 3개 추가:
  - create()                       — INSERT (upsert 아님, 모든 시도 보존)
  - list_by_repo()                 — 최근 시도 목록 (attempted_at DESC)
  - count_failures_by_reason()     — 실패 사유별 카운트 집계
  - find_latest_for_pr()           — PR 최신 시도 행 (Phase 3 PR-B1)
  - mark_actually_merged()         — enabled_pending_merge → actually_merged
  - mark_disabled_externally()     — enabled_pending_merge → disabled_externally
"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.gate import _merge_attempt_states as _states
from src.models.merge_attempt import MergeAttempt


def create(  # pylint: disable=too-many-arguments
    db: Session,
    *,
    analysis_id: int,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    success: bool,
    failure_reason: str | None = None,
    detail_message: str | None = None,
    state: str = _states.LEGACY,
    enabled_at: datetime | None = None,
) -> MergeAttempt:
    """MergeAttempt 레코드를 생성하고 반환한다 (항상 INSERT).

    Phase 3 PR-B1: state + enabled_at 파라미터 추가. 기본값 'legacy' 유지로
    backwards compatible — 기존 호출처는 변경 불필요.
    """
    record = MergeAttempt(
        analysis_id=analysis_id,
        repo_name=repo_name,
        pr_number=pr_number,
        score=score,
        threshold=threshold,
        success=success,
        failure_reason=failure_reason,
        detail_message=detail_message,
        state=state,
        enabled_at=enabled_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_by_repo(
    db: Session,
    repo_name: str,
    limit: int = 50,
) -> list[MergeAttempt]:
    """해당 repo 의 auto-merge 시도 이력 — 최신 시도가 첫 번째."""
    return (
        db.query(MergeAttempt)
        .filter(MergeAttempt.repo_name == repo_name)
        .order_by(MergeAttempt.attempted_at.desc())
        .limit(limit)
        .all()
    )


def count_failures_by_reason(
    db: Session,
    since: datetime | None = None,
) -> dict[str, int]:
    """실패 사유별 카운트 집계 — {failure_reason: count}.

    - success=True 는 제외
    - failure_reason IS NULL 은 집계에서 제외 (정규 태그만 카운트)
    - since 가 주어지면 그 이후(attempted_at >= since) 만
    """
    query = (
        db.query(MergeAttempt.failure_reason, func.count(MergeAttempt.id))  # pylint: disable=not-callable
        .filter(MergeAttempt.success.is_(False))
        .filter(MergeAttempt.failure_reason.is_not(None))
    )
    if since is not None:
        query = query.filter(MergeAttempt.attempted_at >= since)
    query = query.group_by(MergeAttempt.failure_reason)
    return dict(query.all())


def find_latest_for_pr(
    db: Session,
    repo_name: str,
    pr_number: int,
) -> MergeAttempt | None:
    """해당 PR 의 최신 MergeAttempt 행 반환 (없으면 None).

    Phase 3 PR-B1: webhook 핸들러가 `pull_request.closed merged=true` 또는
    `auto_merge_disabled` 수신 시 state 전이 대상 행 식별용.

    Find the latest MergeAttempt row for a PR (Phase 3 PR-B1) — used by the
    webhook lifecycle handlers to locate the row to transition.
    """
    return (
        db.query(MergeAttempt)
        .filter(
            MergeAttempt.repo_name == repo_name,
            MergeAttempt.pr_number == pr_number,
        )
        .order_by(MergeAttempt.attempted_at.desc())
        .first()
    )


def mark_actually_merged(
    db: Session,
    *,
    attempt_id: int,
    merged_at: datetime,
) -> bool:
    """state='enabled_pending_merge' 행만 'actually_merged' 로 전이 (멱등).
    Idempotent transition — only updates rows currently in 'enabled_pending_merge'.

    Returns True if a row was updated, False if no-op (이미 전이됐거나 다른 state).
    Returns True if a row was updated, False otherwise (already transitioned or
    different state — webhook 중복 전송 시 안전).
    """
    rows_updated = (
        db.query(MergeAttempt)
        .filter(
            MergeAttempt.id == attempt_id,
            MergeAttempt.state == _states.ENABLED_PENDING_MERGE,
        )
        .update(
            {
                MergeAttempt.state: _states.ACTUALLY_MERGED,
                MergeAttempt.merged_at: merged_at,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    return rows_updated > 0


def mark_disabled_externally(
    db: Session,
    *,
    attempt_id: int,
    disabled_at: datetime,
    reason: str | None = None,
) -> bool:
    """state='enabled_pending_merge' 행만 'disabled_externally' 로 전이 (멱등).
    Idempotent transition — only updates rows currently in 'enabled_pending_merge'.

    Args:
        reason: 추론된 비활성 사유 (예: "user_disabled", "external_event").
                기존 failure_reason 컬럼에 기록.
                Inferred disable reason — written to the existing failure_reason column.
    """
    update_values: dict = {
        MergeAttempt.state: _states.DISABLED_EXTERNALLY,
        MergeAttempt.disabled_at: disabled_at,
    }
    if reason is not None:
        update_values[MergeAttempt.failure_reason] = reason
    rows_updated = (
        db.query(MergeAttempt)
        .filter(
            MergeAttempt.id == attempt_id,
            MergeAttempt.state == _states.ENABLED_PENDING_MERGE,
        )
        .update(update_values, synchronize_session=False)
    )
    db.commit()
    return rows_updated > 0
