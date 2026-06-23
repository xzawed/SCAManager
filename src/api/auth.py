"""API key authentication dependency for REST API endpoints."""
import logging
from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from src.config import settings
from src.shared.secure_compare import secure_str_compare

logger = logging.getLogger(__name__)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _check_api_key(api_key: str | None = Security(_api_key_header)) -> None:
    if not settings.api_key:
        # 🔴 감사 ①: API_KEY 미설정 시 기본 fail-closed(503) — 명시적 API_AUTH_DISABLED=1 opt-out
        # 시에만 무인증 통과. 이전엔 `app_base_url`이 https 가 아니면(http/빈 값) 통과했는데,
        # 오설정(prod 인데 APP_BASE_URL 이 http 또는 미설정)이면 전체 REST API 가 무인증 노출돼
        # cross-tenant 데이터 유출 위험이 있었다. 이제 노출 여부를 URL 휴리스틱이 아니라 명시적
        # opt-out 플래그로만 결정한다.
        # Audit ①: when API_KEY is unset, fail closed (503) by default; only an explicit
        # API_AUTH_DISABLED=1 opt-out allows keyless access. Previously a non-https (http/empty)
        # app_base_url passed through, so a misconfigured production (APP_BASE_URL set to http or
        # missing) exposed the whole REST API unauthenticated → cross-tenant leak. Exposure is now
        # gated by an explicit flag, not a URL heuristic.
        if settings.api_auth_disabled:
            logger.warning(
                "API_AUTH_DISABLED=1 — all API requests allowed without authentication "
                "(development mode only; never set in production)"
            )
            return
        raise HTTPException(
            status_code=503,
            detail="API key not configured — set API_KEY (or API_AUTH_DISABLED=1 for local development)",
        )
    if not secure_str_compare(api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


require_api_key = Depends(_check_api_key)
