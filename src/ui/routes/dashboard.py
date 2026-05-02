"""Dashboard UI 라우트 — Phase 1 PR 4 (MVP-B 신규 라우트).
Dashboard UI route — replaces deprecated /insights / /insights/me (PR 1~3).

GET /dashboard?days={1|7|30|90} — KPI 4 카드 + 라인 차트 + 자주 발생 이슈.
GET /insights, /insights/me — Phase 1 PR 5: 301 → /dashboard (북마크 보존).
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.services import dashboard_service
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import templates

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    days: int = 7,
):
    """대시보드 — KPI 4 카드 + 점수 추세 차트 + 자주 발생 이슈.
    Dashboard — KPI 4 cards + score trend chart + frequent issues.
    """
    # Telemetry — Phase 1 PR 5 자율 판단 (정책 3): 사용 빈도 측정 1줄, 비식별 (user.id + days).
    # Telemetry: log usage frequency (user.id + days only — no PII).
    logger.info(
        "dashboard_view user_id=%d days=%s",
        current_user.id,
        sanitize_for_log(str(days), max_len=10),
    )

    with SessionLocal() as db:
        kpi = dashboard_service.dashboard_kpi(db, days=days)
        trend = dashboard_service.dashboard_trend(db, days=days)
        frequent_issues = dashboard_service.frequent_issues_v2(db, days=days, n=5)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "current_user": current_user,
            "kpi": kpi,
            "trend": trend,
            "frequent_issues": frequent_issues,
            "days": days,
        },
    )


# ─── Legacy URL Redirects (Phase 1 PR 5) ───────────────────────────────────
# 폐기된 /insights, /insights/me 의 북마크 사용자 보호 — 영구 (301) 리다이렉트.
# Permanent redirect for users with bookmarks of the deprecated URLs.


@router.get("/insights")
def redirect_insights(request: Request) -> RedirectResponse:
    """GET /insights → 301 /dashboard (쿼리 파라미터 보존)."""
    qs = request.url.query
    target = f"/dashboard?{qs}" if qs else "/dashboard"
    return RedirectResponse(url=target, status_code=301)


@router.get("/insights/me")
def redirect_insights_me(request: Request) -> RedirectResponse:
    """GET /insights/me → 301 /dashboard (쿼리 파라미터 보존)."""
    qs = request.url.query
    target = f"/dashboard?{qs}" if qs else "/dashboard"
    return RedirectResponse(url=target, status_code=301)
