"""API key authentication dependency for REST API endpoints."""
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from src.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _check_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_key:
        return
    if api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


require_api_key = Depends(_check_api_key)
