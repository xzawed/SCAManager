"""SCAManager FastAPI application — entry point, lifespan, and router registration."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from alembic import command
from alembic.config import Config

from src.config import settings
from src.database import SessionLocal
from src.shared.http_client import close_http_client, init_http_client
from src.shared.observability import init_sentry
from src.webhook.router import router as webhook_router
from src.api.repos import router as api_repos_router
from src.api.stats import router as api_stats_router
from src.api.hook import router as api_hook_router
from src.ui.router import router as ui_router
from src.auth.github import router as auth_router

logger = logging.getLogger(__name__)


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
    except Exception as exc:
        logger.error("DB migration failed: %s", exc)
    await init_http_client()
    try:
        yield
    finally:
        await close_http_client()


app = FastAPI(title="SCAManager", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=settings.app_base_url.startswith("https"),
    same_site="lax",
    max_age=60 * 60 * 24 * 7,  # 7 days
)
app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(api_repos_router)
app.include_router(api_stats_router)
app.include_router(api_hook_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    """Liveness probe — active_db 필드로 현재 연결 중인 DB를 표시한다.
    Liveness probe — shows the currently connected DB via the active_db field."""
    active = getattr(SessionLocal, "active_db", "primary")
    return {"status": "ok", "active_db": active}


@app.get("/health/tools")
def health_tools():
    """임시 디버그 엔드포인트 — 정적분석 도구 바이너리 경로 확인용. 확인 후 제거 예정.
    Temporary debug endpoint — verifies static analysis tool binary paths. Remove after confirmation."""
    import shutil  # pylint: disable=import-outside-toplevel
    return {
        "rubocop": shutil.which("rubocop"),
        "golangci-lint": shutil.which("golangci-lint"),
        "cppcheck": shutil.which("cppcheck"),
        "slither": shutil.which("slither"),
        "semgrep": shutil.which("semgrep"),
        "shellcheck": shutil.which("shellcheck"),
    }
