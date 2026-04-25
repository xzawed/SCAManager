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
        # 운영환경(HTTPS)에서 API_KEY 미설정 시 전체 API 차단 — 실수로 노출 방지
        # In production (HTTPS), block all API access when API_KEY is not configured.
        if settings.app_base_url.startswith("https"):
            raise HTTPException(
                status_code=503,
                detail="API key not configured — set API_KEY environment variable",
            )
        # 개발환경(HTTP 또는 URL 미설정)에서는 경고 후 통과 허용
        # In development (HTTP or no URL), log a warning but allow through.
        logger.warning("API_KEY is not configured — all requests are allowed (development mode only)")
        return
    if not hmac.compare_digest(api_key or "", settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


require_api_key = Depends(_check_api_key)
