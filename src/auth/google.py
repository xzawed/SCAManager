from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.database import SessionLocal
from src.models.user import User
from src.auth.session import get_current_user

oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
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


@router.get("/auth/google")
async def auth_google(request: Request):
    """Google OAuth 동의 화면으로 리다이렉트."""
    redirect_uri = str(request.url_for("auth_callback"))
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/auth/callback", name="auth_callback")
async def auth_callback(request: Request):
    """Google OAuth 콜백 처리. 유저 upsert 후 세션 저장."""
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})

    google_id = userinfo["sub"]
    email = userinfo["email"]
    display_name = userinfo.get("name", email)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.github_id == google_id).first()
        if not user:
            user = User(github_id=google_id, email=email, display_name=display_name)
            db.add(user)
            db.commit()
            db.refresh(user)
        request.session["user_id"] = user.id
    finally:
        db.close()

    return RedirectResponse(url="/", status_code=302)


@router.post("/auth/logout")
async def logout(request: Request):
    """세션 초기화 후 /login 리다이렉트."""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
