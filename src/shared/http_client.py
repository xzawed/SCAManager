"""HTTP client lifespan singleton — 신뢰 API 전용.

허용 도메인: api.github.com, api.telegram.org, backboard.railway.app.
외부 untrusted webhook (Discord / Slack / 사용자 정의 / n8n) 은
src/notifier/_http.py::build_safe_client() 를 사용해야 한다 (SSRF 방어).

FastAPI lifespan 에서 `init_http_client()` 로 초기화되고 `close_http_client()`
로 정리된다. BackgroundTasks 에서도 접근 가능하도록 모듈 전역 변수를 사용
(request.app.state 경로는 background 실행 시 없을 수 있음).

용도 구분:
- **내부 신뢰 API** (GitHub/Telegram/Railway): 본 모듈의 `get_http_client()`
  사용 (connection pooling, 매 요청 재사용)
- **외부 untrusted webhook** (n8n/discord/slack/custom): `src/notifier/_http.py`
  의 `build_safe_client()` 사용 (SSRF 방어, `follow_redirects=False`, 매
  호출 신규)
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
