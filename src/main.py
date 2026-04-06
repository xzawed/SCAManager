import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from src.webhook.router import router as webhook_router
from src.api.repos import router as api_repos_router
from src.api.stats import router as api_stats_router
from src.ui.router import router as ui_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("DB migration completed")
    except Exception as exc:
        logger.error("DB migration failed: %s", exc)
    yield


app = FastAPI(title="SCAManager", version="0.1.0", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(api_repos_router)
app.include_router(api_stats_router)
app.include_router(ui_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/debug/db")
def debug_db():
    import traceback
    from src.database import engine
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return {"db": "ok", "url_prefix": str(engine.url)[:30]}
    except Exception:
        return {"db": "error", "detail": traceback.format_exc()[-800:]}
