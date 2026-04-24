"""merge_attempt_repo — MergeAttempt 영속화 + 집계 쿼리 단일 출처.

Phase F.1 관측 기반. 3개 공개 함수만 노출:
  - create()                       — INSERT (upsert 아님, 모든 시도 보존)
  - list_by_repo()                 — 최근 시도 목록 (attempted_at DESC)
  - count_failures_by_reason()     — 실패 사유별 카운트 집계 (대시보드/advisor 용)
"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

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
) -> MergeAttempt:
    """MergeAttempt 레코드를 생성하고 반환한다 (항상 INSERT)."""
    record = MergeAttempt(
        analysis_id=analysis_id,
        repo_name=repo_name,
        pr_number=pr_number,
        score=score,
        threshold=threshold,
        success=success,
        failure_reason=failure_reason,
        detail_message=detail_message,
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
