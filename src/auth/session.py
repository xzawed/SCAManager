"""Session helpers — get_current_user() and require_login Depends."""
from dataclasses import dataclass, field
from fastapi import Request, HTTPException
from src.database import SessionLocal
from src.repositories import user_repo


@dataclass
class CurrentUser:
    """세션 사용자 정보 — ORM 세션과 독립된 순수 데이터 컨테이너.
    Session user data — pure data container independent of the ORM session.

    DetachedInstanceError 위험 없이 세션 밖에서 안전하게 사용 가능.
    Safe to use outside the ORM session — no DetachedInstanceError risk.
    """
    id: int
    github_login: str | None
    email: str
    display_name: str
    plaintext_token: str
    # Telegram 연동 여부 — True이면 Telegram 계정이 연결된 상태
    # Whether a Telegram account is linked — True when linked.
    is_telegram_connected: bool = field(default=False)


def get_current_user(request: Request) -> CurrentUser | None:
    """세션에서 현재 사용자를 반환. 없으면 None.
    Return the current user from the session, or None if not logged in.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    with SessionLocal() as db:
        user = user_repo.find_by_id(db, user_id)
        if not user:
            return None
        return CurrentUser(
            id=user.id,
            github_login=user.github_login,
            email=user.email,
            display_name=user.display_name,
            plaintext_token=user.plaintext_token or "",
            # telegram_user_id가 있으면 연동 완료 상태
            # is_telegram_connected is True when telegram_user_id is set.
            is_telegram_connected=user.is_telegram_connected,
        )


def require_login(request: Request) -> CurrentUser:
    """로그인 필수 의존성. 비로그인 시 /login 으로 302 리다이렉트."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user
