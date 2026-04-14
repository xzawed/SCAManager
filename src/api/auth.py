"""API key authentication dependency for REST API endpoints."""
import hmac
import logging
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from src.config import settings

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _check_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_key:
        logger.warning("API_KEY is not configured — all requests are allowed (open access)")
        return
    if not hmac.compare_digest(api_key or "", settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


require_api_key = Depends(_check_api_key)
