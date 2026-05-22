"""GitHub OAuth2 login flow — /auth/github, /auth/callback, /auth/logout."""
import logging
from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from sqlalchemy import update

from src.config import settings
from src.crypto import encrypt_token
from src.database import SessionLocal
from src.models.user import User
from src.repositories import user_repo

logger = logging.getLogger(__name__)

oauth = OAuth()
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",  # nosec B106
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "repo user:email"},
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="src/templates")
# auth/github.py 는 자체 Jinja2Templates 인스턴스 사용 — _helpers.templates 와 분리
# auth/github.py uses its own Jinja2Templates instance — separate from _helpers.templates
from src.i18n.filters import register_i18n_filters  # noqa: E402  # pylint: disable=wrong-import-position
register_i18n_filters(templates.env)


@router.get("/login")
async def login_page(_request: Request):
    """/login → /auth/github 301 리다이렉트 (하위 호환 — 북마크 보존).
    /login → /auth/github 301 redirect (backward compat — preserves bookmarks).
    """
    return RedirectResponse(url="/auth/github", status_code=301)


@router.get("/auth/github")
async def auth_github(request: Request):
    """GitHub OAuth 동의 화면으로 리다이렉트."""
    if settings.app_base_url:
        redirect_uri = settings.app_base_url.rstrip("/") + "/auth/callback"
    else:
        redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.github.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    """GitHub OAuth 콜백. 유저 upsert 후 세션 저장.
    OAuth 오류 시 /?error=oauth_failed, 그 외 예외 시 /?error=auth_failed 로 리다이렉트.
    GitHub OAuth callback. On OAuth error redirect to /?error=oauth_failed,
    on other exceptions redirect to /?error=auth_failed.
    """
    try:
        token = await oauth.github.authorize_access_token(request)
        access_token = encrypt_token(token["access_token"])

        user_resp = await oauth.github.get("user", token=token)
        user_info = user_resp.json()

        emails_resp = await oauth.github.get("user/emails", token=token)
        emails = emails_resp.json()
        github_id = str(user_info["id"])
        primary_email = next(
            (e["email"] for e in emails if e.get("primary") and e.get("verified")),
            # 이메일 미제공 시 GitHub noreply 주소로 폴백 (빈 문자열 저장 방지)
            # Fallback to GitHub noreply address when email is not provided (avoid storing empty string)
            user_info.get("email") or f"{github_id}@users.noreply.github.com",
        )

        github_login = user_info.get("login", "")
        display_name = user_info.get("name") or github_login

        with SessionLocal() as db:
            user = user_repo.find_by_github_id(db, github_id)
            if not user:
                user = User(
                    github_id=github_id,
                    github_login=github_login,
                    github_access_token=access_token,  # 이미 encrypt_token() 적용됨
                    # encrypt_token() already applied before this assignment
                    email=primary_email,
                    display_name=display_name,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                user.github_access_token = access_token  # 이미 encrypt_token() 적용됨
                # encrypt_token() already applied before this assignment
                user.github_login = github_login
                user.display_name = display_name
                db.commit()

            # 세션 고정(Session Fixation) 공격 방어: 인증 완료 후 이전 세션 데이터를 초기화하고
            # 새 세션 ID로 user_id를 저장한다. 공격자가 미리 확보한 세션 ID를 무력화한다.
            # Session Fixation defence: clear any pre-auth session data before storing the
            # authenticated user_id, so an attacker-supplied session token is invalidated.
            request.session.clear()
            request.session["user_id"] = user.id

        return RedirectResponse(url="/", status_code=302)
    except OAuthError:
        # CSRF state 불일치·토큰 거부 등 OAuth 프로토콜 오류
        # OAuth protocol errors: CSRF state mismatch, token rejection, etc.
        logger.warning("OAuth error during GitHub callback")
        return RedirectResponse(url="/?error=oauth_failed", status_code=302)
    except Exception:  # pylint: disable=broad-exception-caught
        # DB 오류·네트워크 오류 등 예상치 못한 예외
        # Unexpected errors: DB failure, network error, etc.
        logger.exception("auth_callback failed unexpectedly")
        return RedirectResponse(url="/?error=auth_failed", status_code=302)


@router.post("/auth/logout")
async def logout(request: Request):
    """세션 초기화 후 / (랜딩 페이지) 리다이렉트.
    HTMX hx-boost 요청은 HX-Redirect 헤더로 전체 페이지 재로드 — landing.html 독립 <head> CSS 보존.
    Redirect to /. HTMX requests use HX-Redirect for full reload so landing.html <head> CSS applies.
    """
    user_id = request.session.get("user_id")
    if user_id:
        # 로그아웃 시 github_access_token 삭제 — 토큰 무기한 잔존 방지
        # Clear github_access_token on logout — prevent stale credential retention
        with SessionLocal() as db:
            db.execute(
                update(User).where(User.id == user_id).values(github_access_token=None)
            )
            db.commit()
    request.session.clear()
    if request.headers.get("HX-Request"):
        # hx-boost body-swap 대신 window.location 전체 재로드 유도
        # Force full page navigation instead of body-swap so landing.html CSS applies
        resp = Response(status_code=200)
        resp.headers["HX-Redirect"] = "/"
        return resp
    return RedirectResponse(url="/", status_code=302)
