from fastapi import Request, HTTPException
from src.database import SessionLocal
from src.models.user import User


def get_current_user(request: Request):
    """세션에서 현재 사용자를 반환. 없으면 None."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()


def require_login(request: Request) -> User:
    """로그인 필수 의존성. 비로그인 시 /login 으로 302 리다이렉트."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user
