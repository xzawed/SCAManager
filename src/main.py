"""SCAManager FastAPI application — entry point, lifespan, and router registration."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from alembic import command
from alembic.config import Config

from src.config import settings
from src.shared.http_client import close_http_client, init_http_client
from src.shared.observability import init_sentry
from src.webhook.router import router as webhook_router
from src.api.repos import router as api_repos_router
from src.api.stats import router as api_stats_router
from src.api.hook import router as api_hook_router
from src.api.users import router as api_users_router
from src.api.internal_cron import router as api_internal_cron_router
from src.api.insights import router as api_insights_router
from src.ui.router import router as ui_router
from src.auth.github import router as auth_router

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """보안 응답 헤더를 모든 응답에 추가한다.
    Adds security response headers to all responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if settings.app_base_url.startswith("https"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


def _run_migrations() -> None:
    """Run Alembic migrations to head."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Run DB migrations on startup, then yield control to the application."""
    if settings.session_secret == "dev-secret-change-in-production":
        logger.warning(
            "SESSION_SECRET is using the default insecure value — "
            "set SESSION_SECRET environment variable in production!"
        )
    if not (settings.anthropic_api_key or "").strip():
        logger.warning(
            "ANTHROPIC_API_KEY is empty — AI 리뷰가 비활성화됩니다. "
            "모든 분석이 기본값(89/B)으로 fallback 됩니다. "
            "Railway Variables 또는 .env 에 키를 설정하세요."
        )
    is_prod_like = settings.app_base_url.startswith("https")
    if is_prod_like and not (settings.token_encryption_key or "").strip():
        logger.warning(
            "SECURITY: TOKEN_ENCRYPTION_KEY is not set in production "
            "(APP_BASE_URL=%s). GitHub OAuth tokens will be stored in plaintext. "
            "Generate with: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"",
            settings.app_base_url,
        )
    init_sentry()  # Sentry SDK — SENTRY_DSN 설정 시만 활성
    try:
        await asyncio.wait_for(asyncio.to_thread(_run_migrations), timeout=30)
        logger.info("DB migration completed")
    except asyncio.TimeoutError:
        logger.error("DB migration timed out after 30s — starting app anyway")
    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.error("DB migration failed: %s", exc)
    await init_http_client()
    try:
        yield
    finally:
        await close_http_client()


_is_prod = settings.app_base_url.startswith("https")

app = FastAPI(
    title="SCAManager",
    version="0.1.0",
    lifespan=lifespan,
    # /docs, /redoc 프로덕션 환경에서 비활성화 — API 구조 정보 노출 방지
    # Disable /docs and /redoc in production to prevent API structure disclosure.
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
    openapi_url=None if _is_prod else "/openapi.json",
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=_is_prod,
    same_site="lax",
    max_age=60 * 60 * 24 * 7,  # 7 days
)
app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(api_repos_router)
app.include_router(api_stats_router)
app.include_router(api_hook_router)
app.include_router(api_users_router)
app.include_router(api_internal_cron_router)
app.include_router(api_insights_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    """Liveness probe — Railway/infra 헬스체크용. 내부 구현 세부사항은 노출하지 않는다.
    Liveness probe for Railway/infra health checks. Does not expose implementation details."""
    return {"status": "ok"}
