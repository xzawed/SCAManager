"""merge_retry_repo — MergeRetryQueue 기본 CRUD 단일 출처 (Phase 12 T1).

기본 CRUD 4개 함수만 노출 (claim 의미론은 T6 에서 추가):
  - get()                   — 기본 키 조회
  - list_pending()          — 처리 대상 pending 행 목록 (next_retry_at <= now)
  - get_by_sha()            — (repo_full_name, commit_sha) 로 비종료 행 조회
  - delete_all_for_repo()   — repo 전체 행 하드 삭제 (cascade 정리용)
"""
from datetime import datetime

from sqlalchemy.orm import Session

from src.models.merge_retry import MergeRetryQueue

# 비종료 상태 — 이 상태의 행만 get_by_sha 에서 반환한다
# Non-terminal statuses — get_by_sha only returns rows with these statuses.
_NON_TERMINAL_STATUSES = {"pending"}


def get(db: Session, row_id: int) -> MergeRetryQueue | None:
    """기본 키로 MergeRetryQueue 행을 조회한다.
    Fetch a MergeRetryQueue row by primary key.
    """
    return db.query(MergeRetryQueue).filter(MergeRetryQueue.id == row_id).first()


def list_pending(
    db: Session,
    *,
    now: datetime,
    limit: int = 50,
) -> list[MergeRetryQueue]:
    """재시도 대상 pending 행 목록 — status='pending' AND next_retry_at <= now.

    next_retry_at ASC 정렬 — 가장 오래된 예정 행 우선 처리.
    Returns pending rows due for retry, ordered by next_retry_at ASC (oldest first).
    """
    return (
        db.query(MergeRetryQueue)
        .filter(
            MergeRetryQueue.status == "pending",
            MergeRetryQueue.next_retry_at <= now,
        )
        .order_by(MergeRetryQueue.next_retry_at.asc())
        .limit(limit)
        .all()
    )


def get_by_sha(
    db: Session,
    *,
    repo_full_name: str,
    commit_sha: str,
) -> MergeRetryQueue | None:
    """(repo_full_name, commit_sha) 로 비종료 상태 행 첫 번째를 조회한다.

    비종료: status = 'pending' (T6 이후 확장 가능).
    Fetch the first non-terminal row for (repo_full_name, commit_sha).
    Non-terminal: status = 'pending' (extendable in T6+).
    """
    return (
        db.query(MergeRetryQueue)
        .filter(
            MergeRetryQueue.repo_full_name == repo_full_name,
            MergeRetryQueue.commit_sha == commit_sha,
            MergeRetryQueue.status.in_(_NON_TERMINAL_STATUSES),
        )
        .first()
    )


def delete_all_for_repo(
    db: Session,
    *,
    repo_full_name: str,
) -> int:
    """해당 repo 의 모든 MergeRetryQueue 행을 하드 삭제하고 삭제 수를 반환한다.

    리포 삭제 cascade 정리용 — Analysis ON DELETE CASCADE 와 함께 고아 레코드 방지.
    Hard-deletes all rows for the given repo and returns the count deleted.
    Used for repo cascade cleanup — complements Analysis ON DELETE CASCADE.
    """
    count = (
        db.query(MergeRetryQueue)
        .filter(MergeRetryQueue.repo_full_name == repo_full_name)
        .delete(synchronize_session=False)
    )
    db.commit()
    return count
