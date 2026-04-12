"""SCAManager FastAPI application — entry point, lifespan, and router registration."""
import asyncio
import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from src.config import settings
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
    try:
        await asyncio.wait_for(asyncio.to_thread(_run_migrations), timeout=30)
        logger.info("DB migration completed")
    except asyncio.TimeoutError:
        logger.error("DB migration timed out after 30s — starting app anyway")
    except Exception as exc:  # noqa: BLE001 — 마이그레이션 실패가 앱 시작을 막아선 안 됨
        logger.error("DB migration failed: %s", exc)
    yield


app = FastAPI(title="SCAManager", version="0.1.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret)
app.include_router(auth_router)
app.include_router(webhook_router)
app.include_router(api_repos_router)
app.include_router(api_stats_router)
app.include_router(api_hook_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    """Liveness probe — returns 200 OK when the application is running."""
    return {"status": "ok"}
