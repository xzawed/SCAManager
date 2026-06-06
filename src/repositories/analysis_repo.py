"""AnalysisRepo — Analysis ORM 쿼리 단일 출처."""
import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.models.analysis import Analysis

logger = logging.getLogger(__name__)


def find_by_sha(db: Session, commit_sha: str, repo_id: int) -> Analysis | None:
    """commit SHA + repo_id 조합으로 조회 (중복 체크·멱등성용)."""
    return db.query(Analysis).filter_by(commit_sha=commit_sha, repo_id=repo_id).first()


def find_by_id(db: Session, analysis_id: int) -> Analysis | None:
    """PK로 조회."""
    return db.query(Analysis).filter_by(id=analysis_id).first()


def save_new(db: Session, analysis: Analysis) -> tuple[Analysis, bool]:
    """신규 Analysis를 저장하고 (analysis, created) 를 반환한다.
    Save a new Analysis and return (analysis, created).

    created=True = 신규 삽입. created=False = DB unique constraint(uq_analyses_repo_sha) 위반으로
    기존 레코드를 반환 (동시 insert race — pipeline TOCTOU 완화 이후 마지막 안전망).
    created=False 는 호출자가 중복 알림/게이트를 차단하는 신호다.
    created=False signals the caller to skip duplicate notify/gate (concurrent-insert race).
    """
    try:
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis, True
    except IntegrityError:
        db.rollback()
        logger.warning(
            "Duplicate analysis insert blocked by DB constraint (repo_id=%s, sha=%s)",
            analysis.repo_id,
            analysis.commit_sha,
        )
        existing = find_by_sha(db, analysis.commit_sha, analysis.repo_id)
        if existing is None:
            raise
        return existing, False


def delete_by_repo_id(db: Session, repo_id: int) -> int:
    """Repository FK 기반 Analysis 전체 삭제. 삭제된 행 수 반환. 호출자가 commit."""
    return db.query(Analysis).filter_by(repo_id=repo_id).delete(
        synchronize_session=False
    )
