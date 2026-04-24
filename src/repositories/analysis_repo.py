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


def save_new(db: Session, analysis: Analysis) -> Analysis:
    """신규 Analysis를 저장하고 DB에서 refresh한 뒤 반환한다.

    DB unique constraint(uq_analyses_repo_sha) 위반 시 기존 레코드를 반환.
    pipeline의 TOCTOU 완화 이후 마지막 안전망.
    """
    try:
        db.add(analysis)
        db.commit()
        db.refresh(analysis)
        return analysis
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
        return existing


def delete_by_repo_id(db: Session, repo_id: int) -> int:
    """Repository FK 기반 Analysis 전체 삭제. 삭제된 행 수 반환. 호출자가 commit."""
    return db.query(Analysis).filter_by(repo_id=repo_id).delete(
        synchronize_session=False
    )
