"""UserRepo — User ORM 쿼리 단일 출처.

Note: filter() 기반 — 기존 mock 패턴 (`db.query(...).filter(...).first()`)
호환 유지.
"""
from sqlalchemy.orm import Session

from src.models.user import User


def find_by_id(db: Session, user_id: int) -> User | None:
    """PK 로 조회."""
    return db.query(User).filter(User.id == user_id).first()


def find_by_github_id(db: Session, github_id: str) -> User | None:
    """GitHub 계정 ID(문자열) 로 조회 (OAuth 로그인 경로)."""
    return db.query(User).filter(User.github_id == github_id).first()
