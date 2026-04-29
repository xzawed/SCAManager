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

# Phase 2 — 명시적 connection pool 한도 (httpx 기본값 100/20 보다 여유)
# Phase 2 — explicit connection-pool limits (more headroom than httpx default 100/20)
# 폭주 시나리오 (monorepo check_suite 50개 동시 + 알림 6채널 fan-out + retry queue):
# - max_connections: 200 (peak 동시 호출 + Railway single instance)
# - max_keepalive_connections: 50 (warm pool 비율 1/4)
# - keepalive_expiry: 30초 (DNS rebinding 회피 + Railway IPv6 환경 호환)
# 14-에이전트 감사에서 식별된 R3-A concurrency / R3-B performance 권고.
_HTTP_LIMITS = httpx.Limits(
    max_connections=200,
    max_keepalive_connections=50,
    keepalive_expiry=30.0,
)

_client: httpx.AsyncClient | None = None


async def init_http_client() -> None:
    """FastAPI lifespan startup 에서 호출 — 전역 httpx.AsyncClient 생성."""
    global _client  # pylint: disable=global-statement
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=HTTP_CLIENT_TIMEOUT,
            limits=_HTTP_LIMITS,
        )
        logger.info(
            "HTTP client initialized (singleton, max_conn=%d, keepalive=%d)",
            _HTTP_LIMITS.max_connections, _HTTP_LIMITS.max_keepalive_connections,
        )


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
