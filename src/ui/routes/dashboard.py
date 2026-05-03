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
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.services import dashboard_service
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import templates

logger = logging.getLogger(__name__)

router = APIRouter()


_VALID_MODES = ("overview", "insight")

# Phase 3 PR 4 — 사용자 신호 기반 default 모드 임계값.
# Claude narrative 가 의미있게 생성되려면 최소 N건의 분석 컨텍스트가 필요.
# Phase 3 PR 4 — User-signal-based default mode threshold.
# Claude narrative needs at least N analyses for meaningful context.
_INSIGHT_AUTO_DEFAULT_THRESHOLD = 5


def _detect_initial_dashboard_mode(db: Session) -> str:
    """URL ?mode= 부재 + localStorage 비어있을 때 서버 fallback default 모드.

    Server fallback when URL `?mode=` is absent and localStorage is empty.

    시그널 우선순위:
    1. settings.anthropic_api_key 미설정 → 'overview' (Insight 모드 비가용)
    2. Analysis count < _INSIGHT_AUTO_DEFAULT_THRESHOLD → 'overview' (narrative 컨텍스트 부족)
    3. 그 외 → 'insight' (사용자가 AI 가치 즉시 체험)

    Signals:
    1. anthropic_api_key empty → 'overview' (Insight unavailable)
    2. Analysis count below threshold → 'overview' (insufficient context)
    3. Otherwise → 'insight' (give the user the AI benefit on first visit)
    """
    if not settings.anthropic_api_key:
        return "overview"
    count = db.scalar(select(func.count(Analysis.id))) or 0  # pylint: disable=not-callable
    if int(count) < _INSIGHT_AUTO_DEFAULT_THRESHOLD:
        return "overview"
    return "insight"


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    days: int = 7,
    mode: str | None = None,
):
    """대시보드 — Phase 3 PR 3 mode 분기 + PR 4 사용자 신호 기반 default.

    Dashboard with Phase 3 PR 3 mode branch + PR 4 user-signal-based default.

    - mode=overview: KPI 5 카드 + 점수 추세 + 자주 발생 이슈 + Auto-merge + feedback CTA
    - mode=insight: Claude AI 4 카드 narrative (✨ positive / 🔍 focus / 📊 metrics / 💬 next)
    - mode=None / 비-whitelist: server fallback (`_detect_initial_dashboard_mode`) — API key + 데이터 시그널
    - 클라이언트 JS (PR 4) 가 localStorage 우선 적용 후 redirect (FOUC 최소)
    """
    with SessionLocal() as db:
        # URL ?mode= 명시 우선, 없거나 invalid 면 서버 fallback (사용자 신호 기반 default)
        # URL ?mode= takes precedence; server fallback otherwise (user-signal-based default)
        if mode in _VALID_MODES:
            effective_mode = mode
        else:
            effective_mode = _detect_initial_dashboard_mode(db)

        # Telemetry — Phase 1 PR 5 자율 판단 (정책 3) + Phase 3 PR 3/4 mode 추가, 비식별.
        # Telemetry: log usage frequency (user.id + days + effective_mode + url_mode flag — no PII).
        logger.info(
            "dashboard_view user_id=%d days=%s mode=%s url_mode=%s",
            current_user.id,
            sanitize_for_log(str(days), max_len=10),
            sanitize_for_log(effective_mode, max_len=20),
            "1" if mode in _VALID_MODES else "0",
        )

        if effective_mode == "insight":
            # Phase 3 PR 2 — Claude AI 4 카드 narrative (caching 적용).
            # Phase 3 PR 2 — Claude AI 4-card narrative (with caching).
            insight = await dashboard_service.insight_narrative(db, days=days)
            return templates.TemplateResponse(
                request,
                "dashboard.html",
                {
                    "current_user": current_user,
                    "mode": "insight",
                    "initial_mode": effective_mode,  # PR 4 — 클라이언트 JS data-initial-mode 신호
                    "insight": insight,
                    "days": days,
                },
            )

        # effective_mode == "overview" — 기존 동작 보존
        # effective_mode == "overview" — preserves prior behavior
        kpi = dashboard_service.dashboard_kpi(db, days=days)
        trend = dashboard_service.dashboard_trend(db, days=days)
        frequent_issues = dashboard_service.frequent_issues_v2(db, days=days, n=5)
        # Phase 2 PR 1: Auto-merge KPI + 실패 분포.
        auto_merge = dashboard_service.auto_merge_kpi(db, days=days)
        merge_failures = dashboard_service.merge_failure_distribution(db, days=days, n=5)
        # Phase 2 PR 2 (2026-05-02): feedback CTA — 운영 row=0 → 사용자 행동 유도.
        feedback = dashboard_service.feedback_status(db)

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "current_user": current_user,
            "mode": "overview",
            "initial_mode": effective_mode,  # PR 4 — 클라이언트 JS data-initial-mode 신호
            "kpi": kpi,
            "trend": trend,
            "frequent_issues": frequent_issues,
            "auto_merge": auto_merge,
            "merge_failures": merge_failures,
            "feedback": feedback,
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
