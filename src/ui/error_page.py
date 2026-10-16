"""브라우저 화면 요청의 404·403 은 오류 «화면» — API·비브라우저 요청은 FastAPI 기본(JSON) 그대로.

Browser page requests get an error page for 404/403; everything else keeps FastAPI's default JSON.

없는 리포·분석 주소(삭제된 리포 · 알림 속 옛 링크 · 남의 리포)로 가면 브라우저에
`{"detail": "..."}` 원문이 보였다(2026-10-16 렌더링 검수). 사용자 결정 = «브라우저 요청만».
🔴 hx-boost 링크 클릭(XHR, `Accept: */*`)은 여기 해당하지 않는다 — htmx 는 4xx 를 교체하지 않는다.
"""
from __future__ import annotations

import logging

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.auth.session import get_current_user
from src.ui._helpers import get_locale, templates

logger = logging.getLogger(__name__)

# 오류 «화면» 으로 그리는 상태 — 그 밖(401·405·422·5xx)은 기본 처리기가 맡는다.
# Statuses rendered as an error page; the default handler keeps every other status.
_PAGE_STATUSES = frozenset({403, 404})
# 화면이 아닌 경로 — 브라우저가 직접 열어도 JSON 계약을 지킨다.
# Non-page paths keep their JSON contract even when a browser opens them.
_NON_PAGE_PREFIXES = ("/api/", "/webhooks/", "/static/", "/health", "/internal/", "/auth/", "/mcp")


def wants_error_page(request: Request) -> bool:
    """GET · 화면 경로 · `Accept` 의 미디어 타입 목록에 `text/html` 이 «있을» 때만 True.

    True only for a GET to a page path whose Accept header lists the text/html media type.
    """
    if request.method != "GET" or request.url.path.startswith(_NON_PAGE_PREFIXES):
        return False
    accept = request.headers.get("accept", "")
    media_types = {part.split(";", 1)[0].strip().lower() for part in accept.split(",")}
    return "text/html" in media_types


async def html_aware_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """404·403 화면 요청 → `error.html`(상태 코드 유지). 나머지 → FastAPI 기본 JSON."""
    if exc.status_code not in _PAGE_STATUSES or not wants_error_page(request):
        return await http_exception_handler(request, exc)
    try:
        # 세션 조회는 동기 DB — 루프 밖에서. / Session lookup is sync DB work; keep it off the loop.
        user = await run_in_threadpool(get_current_user, request)
    except Exception:  # pylint: disable=broad-exception-caught
        # 오류 화면을 그리다 또 실패하면 안 된다 — 비로그인 nav 로 그린다.
        # Rendering the error page must not fail again; fall back to the anonymous nav.
        logger.warning("error page: current user lookup failed", exc_info=True)
        user = None
    return templates.TemplateResponse(
        request,
        "error.html",
        {"current_user": user, "locale": get_locale(request), "status_code": exc.status_code},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )
