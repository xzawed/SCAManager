"""issue_registration_repo — IssueRegistration CRUD + 중복 조회 단일 출처.
issue_registration_repo — single source for IssueRegistration CRUD and dedup lookup.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.issue_registration import IssueRegistration


def find_by_key(db: Session, *, repo_id: int, issue_key: str) -> IssueRegistration | None:
    """repo_id + issue_key 로 기존 등록 이력을 조회한다.
    Look up an existing registration by repo_id and issue_key.
    """
    return (
        db.query(IssueRegistration)
        .filter(
            IssueRegistration.repo_id == repo_id,
            IssueRegistration.issue_key == issue_key,
        )
        .first()
    )


def create(
    db: Session,
    *,
    analysis_id: int,
    repo_id: int,
    issue_type: str,
    issue_key: str,
    github_issue_number: int,
) -> IssueRegistration:
    """Issue 등록 이력을 INSERT하고 반환한다.
    Insert a new registration record and return it.
    """
    record = IssueRegistration(
        analysis_id=analysis_id,
        repo_id=repo_id,
        issue_type=issue_type,
        issue_key=issue_key,
        github_issue_number=github_issue_number,
        github_issue_state="open",
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_by_analysis(db: Session, *, analysis_id: int) -> list[IssueRegistration]:
    """특정 분석의 모든 등록 이력을 반환한다.
    Return all registrations for a given analysis.
    """
    return (
        db.query(IssueRegistration)
        .filter(IssueRegistration.analysis_id == analysis_id)
        .all()
    )


def list_by_repo(db: Session, *, repo_id: int) -> list[IssueRegistration]:
    """특정 리포의 모든 등록 이력을 최신순으로 반환한다.
    Return all registrations for a given repo, newest first.
    """
    return (
        db.query(IssueRegistration)
        .filter(IssueRegistration.repo_id == repo_id)
        .order_by(IssueRegistration.created_at.desc())
        .all()
    )


def update_state(db: Session, *, record: IssueRegistration, state: str) -> None:
    """GitHub Issue 상태와 동기화 시각을 갱신한다.
    Update the GitHub Issue state and sync timestamp.
    """
    record.github_issue_state = state
    record.github_issue_synced_at = datetime.now(timezone.utc)
    db.commit()
