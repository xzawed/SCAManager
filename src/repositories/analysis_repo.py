"""AnalysisRepo — Analysis ORM 쿼리 단일 출처."""
from sqlalchemy.orm import Session
from src.models.analysis import Analysis


def find_by_sha(db: Session, commit_sha: str, repo_id: int) -> Analysis | None:
    """commit SHA + repo_id 조합으로 조회 (중복 체크·멱등성용)."""
    return db.query(Analysis).filter_by(commit_sha=commit_sha, repo_id=repo_id).first()


def find_by_id(db: Session, analysis_id: int) -> Analysis | None:
    """PK로 조회."""
    return db.query(Analysis).filter_by(id=analysis_id).first()


def save_new(db: Session, analysis: Analysis) -> Analysis:
    """신규 Analysis를 저장하고 DB에서 refresh한 뒤 반환한다."""
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


def delete_by_repo_id(db: Session, repo_id: int) -> int:
    """Repository FK 기반 Analysis 전체 삭제. 삭제된 행 수 반환. 호출자가 commit."""
    return db.query(Analysis).filter_by(repo_id=repo_id).delete(
        synchronize_session=False
    )
