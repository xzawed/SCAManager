"""Dashboard UI 라우트 — Phase 1 PR 4 (MVP-B 신규 라우트).
Dashboard UI route — replaces deprecated /insights / /insights/me (PR 1~3).

GET /dashboard?days={1|7|30|90} — KPI 4 카드 + 라인 차트 + 자주 발생 이슈.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.services import dashboard_service
from src.ui._helpers import templates

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
