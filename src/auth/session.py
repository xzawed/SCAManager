"""Session helpers — get_current_user() and require_login Depends."""
from dataclasses import dataclass, field
from fastapi import Request, HTTPException
from src.config import settings
from src.database import SessionLocal
from src.repositories import user_repo
from src.shared.feature_kill_switch import is_disabled


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


def _parse_admin_emails(raw: str) -> set[str]:
    """CSV 형식 admin email allow-list 파싱 — 공백 trim + lowercase 정규화.

    Parse CSV admin email allow-list — strip + lowercase.
    """
    return {e.strip().lower() for e in (raw or "").split(",") if e.strip()}


def require_admin(request: Request) -> CurrentUser:
    """SaaS admin 영역 접근 필수 의존성 (Cycle 79 PR 2 신설).

    SaaS admin area access dependency (Cycle 79 PR 2).

    3 layer 검증:
    1. kill-switch (`SAAS_MULTITENANT_DISABLED=1`) → 503 (멀티 테넌트 영역 비활성)
    2. require_login → 401 (비로그인)
    3. user.email in `SAAS_ADMIN_EMAILS` → 403 (admin 부재)
    """
    # Layer 1: kill-switch (Phase 9 패턴 — feature_kill_switch helper 활용)
    # Layer 1: kill-switch (Phase 9 pattern — feature_kill_switch helper)
    if is_disabled("SAAS_MULTITENANT"):
        raise HTTPException(status_code=503, detail="SaaS admin area disabled")

    # Layer 2: require_login (기존 패턴 차용)
    # Layer 2: require_login (existing pattern)
    user = require_login(request)

    # Layer 3: admin email allow-list 검증
    # Layer 3: admin email allow-list check
    allowed = _parse_admin_emails(settings.saas_admin_emails)
    if not allowed:
        # Allow-list 미설정 = 모든 사용자 차단 (silent open access 회피)
        # Allow-list unset = block all (avoid silent open access)
        raise HTTPException(status_code=503, detail="SAAS_ADMIN_EMAILS unset")
    if (user.email or "").lower() not in allowed:
        raise HTTPException(status_code=403, detail="admin access required")
    return user
