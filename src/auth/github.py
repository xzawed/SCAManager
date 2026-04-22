"""GitHub OAuth2 login flow — /login, /auth/github, /auth/callback, /auth/logout."""
import logging
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.crypto import encrypt_token
from src.database import SessionLocal
from src.models.user import User
from src.repositories import user_repo
from src.auth.session import get_current_user

logger = logging.getLogger(__name__)

oauth = OAuth()
oauth.register(
    name="github",
    client_id=settings.github_client_id,
    client_secret=settings.github_client_secret,
    access_token_url="https://github.com/login/oauth/access_token",
    authorize_url="https://github.com/login/oauth/authorize",
    api_base_url="https://api.github.com/",
    client_kwargs={"scope": "repo user:email"},
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="src/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """로그인 페이지. 이미 로그인된 경우 / 로 리다이렉트."""
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {})


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
    """GitHub OAuth 콜백. 유저 upsert 후 세션 저장."""
    token = await oauth.github.authorize_access_token(request)
    access_token = encrypt_token(token["access_token"])

    user_resp = await oauth.github.get("user", token=token)
    user_info = user_resp.json()

    emails_resp = await oauth.github.get("user/emails", token=token)
    emails = emails_resp.json()
    primary_email = next(
        (e["email"] for e in emails if e.get("primary") and e.get("verified")),
        user_info.get("email") or "",
    )

    github_id = str(user_info["id"])
    github_login = user_info.get("login", "")
    display_name = user_info.get("name") or github_login

    with SessionLocal() as db:
        user = user_repo.find_by_github_id(db, github_id)
        if not user:
            user = User(
                github_id=github_id,
                github_login=github_login,
                github_access_token=access_token,  # 이미 encrypt_token() 적용됨
                email=primary_email,
                display_name=display_name,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user.github_access_token = access_token  # 이미 encrypt_token() 적용됨
            user.github_login = github_login
            user.display_name = display_name
            db.commit()
        request.session["user_id"] = user.id  # 세션 닫히기 전에 id 저장

    return RedirectResponse(url="/", status_code=302)


@router.post("/auth/logout")
async def logout(request: Request):
    """세션 초기화 후 /login 리다이렉트."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
