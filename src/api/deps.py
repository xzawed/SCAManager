"""API 공용 의존성 — DB 세션 내 공통 조회 헬퍼."""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from src.models.repository import Repository


def get_repo_or_404(repo_name: str, db: Session) -> Repository:
    """DB에서 Repository를 조회하고 없으면 HTTP 404를 발생시킨다."""
    repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo
