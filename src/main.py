import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from src.webhook.router import router as webhook_router

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


@app.get("/health")
def health():
    return {"status": "ok"}
