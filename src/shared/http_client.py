"""httpx.AsyncClient lifespan 싱글톤 — 내부 신뢰 API 호출용.

FastAPI lifespan 에서 `init_http_client()` 로 초기화되고 `close_http_client()`
로 정리된다. BackgroundTasks 에서도 접근 가능하도록 모듈 전역 변수를 사용
(request.app.state 경로는 background 실행 시 없을 수 있음).

주의 — 용도 구분:
- **외부 untrusted webhook** (n8n/discord/slack/custom): `src/notifier/_http.py`
  의 `build_safe_client()` 사용 (SSRF 방어, `follow_redirects=False`, 매
  호출 신규)
- **내부 신뢰 API** (GitHub/Telegram/Railway): 본 모듈의 `get_http_client()`
  사용 (connection pooling, 매 요청 재사용)

현재는 인프라만 제공하며 실제 호출 사이트 치환은 후속 Phase 에서 단계적
진행 (15곳 mock 경로 재작성 필요).
"""
from __future__ import annotations

import logging

import httpx

from src.constants import HTTP_CLIENT_TIMEOUT

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


async def init_http_client() -> None:
    """FastAPI lifespan startup 에서 호출 — 전역 httpx.AsyncClient 생성."""
    global _client  # pylint: disable=global-statement
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=HTTP_CLIENT_TIMEOUT)
        logger.info("HTTP client initialized (singleton)")


async def close_http_client() -> None:
    """FastAPI lifespan shutdown 에서 호출 — 전역 client 정리."""
    global _client  # pylint: disable=global-statement
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        logger.info("HTTP client closed")
    _client = None


def get_http_client() -> httpx.AsyncClient:
    """현재 전역 httpx.AsyncClient 반환 — lifespan 외부 호출 시 RuntimeError."""
    if _client is None or _client.is_closed:
        raise RuntimeError(
            "HTTP client not initialized — lifespan 이 init_http_client() 를 호출해야 합니다."
        )
    return _client
