"""Dashboard UI 라우트 — Phase 1 PR 4 (MVP-B 신규 라우트).
Dashboard UI route — replaces deprecated /insights / /insights/me (PR 1~3).

GET /dashboard?days={1|7|30|90} — KPI 4 카드 + 라인 차트 + 자주 발생 이슈.
GET /insights, /insights/me — Phase 1 PR 5: 301 → /dashboard (북마크 보존).
"""
from __future__ import annotations

import logging
from datetime import datetime
from datetime import timezone as _tz
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.repositories import repository_repo
from src.services import dashboard_service
from src.services.repo_insight_service import (
    repo_ai_suggestions,
    repo_category_breakdown,
    repo_kpi,
    repo_recurring_issues,
    repo_score_trend,
)
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import get_locale, templates  # noqa: F401  # get_locale = Phase 2 PR-6 페어

logger = logging.getLogger(__name__)

router = APIRouter()

_DASHBOARD_TEMPLATE = "dashboard.html"

_VALID_MODES = ("overview", "insight", "security", "usage", "repos")

# Phase 3 PR 4 — 사용자 신호 기반 default 모드 임계값.
# Claude narrative 가 의미있게 생성되려면 최소 N건의 분석 컨텍스트가 필요.
# Phase 3 PR 4 — User-signal-based default mode threshold.
# Claude narrative needs at least N analyses for meaningful context.
_INSIGHT_AUTO_DEFAULT_THRESHOLD = 5


def _detect_initial_dashboard_mode(db: Session, user_id: int | None = None) -> str:
    """URL ?mode= 부재 + localStorage 비어있을 때 서버 fallback default 모드.

    Server fallback when URL `?mode=` is absent and localStorage is empty.
    Phase 3 PR 5: `user_id` 명시 시 사용자별 분석 count 기준 (RLS 정합).

    시그널 우선순위:
    1. settings.anthropic_api_key 미설정 → 'overview' (Insight 모드 비가용)
    2. (user_id 격리된) Analysis count < _INSIGHT_AUTO_DEFAULT_THRESHOLD → 'overview'
    3. 그 외 → 'insight' (사용자가 AI 가치 즉시 체험)
    """
    if not settings.anthropic_api_key:
        return "overview"
    count_q = select(func.count(Analysis.id))  # pylint: disable=not-callable
    if user_id is not None:
        # PR 5 — Repository.user_id 기반 사용자별 분석 count (legacy NULL 호환)
        count_q = count_q.join(Repository, Analysis.repo_id == Repository.id).where(
            (Repository.user_id == user_id) | (Repository.user_id.is_(None))
        )
    count = db.scalar(count_q) or 0
    if int(count) < _INSIGHT_AUTO_DEFAULT_THRESHOLD:
        return "overview"
    return "insight"


_REPORT_WARNING_GRADES = {"D", "F"}


def _build_repo_summary(db: Session, user_id: int, days: int) -> dict:
    """repos 모드 상단 요약 데이터 빌드 — KPI + 등급 분포 + 경고 Repo 목록.

    Build repos mode top summary: KPI, grade distribution, warning repos.
    """
    repos = repository_repo.find_all_by_user(db, user_id)
    now = datetime.now(_tz.utc)

    grade_dist: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    warning_repos: list[dict] = []
    total_scores: list[float] = []
    repo_rows: list[dict] = []

    for repo in repos:
        kpi = repo_kpi(db, repo.id, days, now=now)
        grade = kpi["grade"]
        warning = grade in _REPORT_WARNING_GRADES or kpi["high_security_count"] > 0
        if grade in grade_dist:
            grade_dist[grade] += 1
        if kpi["avg_score"] is not None:
            total_scores.append(kpi["avg_score"])
        row = {
            "repo_id": repo.id,
            "full_name": repo.full_name,
            "avg_score": kpi["avg_score"],
            "grade": grade,
            "score_delta": kpi["score_delta"],
            "warning": warning,
        }
        repo_rows.append(row)
        if warning:
            warning_repos.append(row)

    # 경고 Repo는 점수 낮은 순 정렬 (None은 맨 뒤)
    # Sort warning repos by score ascending (None last)
    warning_repos.sort(key=lambda r: (r["avg_score"] is None, r["avg_score"] or 0))

    global_avg = (
        round(sum(total_scores) / len(total_scores), 1) if total_scores else None
    )

    return {
        "repos": repo_rows,
        "summary": {
            "total_repos": len(repos),
            "avg_score": global_avg,
            "grade_distribution": grade_dist,
            "warning_count": len(warning_repos),
        },
        "warning_repos": warning_repos,
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(  # pylint: disable=too-many-locals
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    days: int = Query(default=7, ge=1, le=365),
    mode: str | None = None,
    refresh: int = 0,
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
            effective_mode = _detect_initial_dashboard_mode(db, user_id=current_user.id)

        # Telemetry — Phase 1 PR 5 자율 판단 (정책 3) + Phase 3 PR 3/4 mode 추가, 비식별.
        # Telemetry: log usage frequency (user.id + days + effective_mode + url_mode flag — no PII).
        logger.info(
            "dashboard_view user_id=%d days=%s mode=%s url_mode=%s",
            current_user.id,
            sanitize_for_log(str(days), max_len=10),
            sanitize_for_log(effective_mode, max_len=20),
            "1" if mode in _VALID_MODES else "0",
        )

        # Phase 2 PR-6 — locale context 4 분기 모두 주입 의무 (LocaleMiddleware 페어)
        # Phase 2 PR-6 — inject locale context to all 4 branches (pairs with LocaleMiddleware)
        locale_value = get_locale(request)

        if effective_mode == "repos":
            # repos 모드 — 포트폴리오 요약 + 선택된 Repo 상세 레포트
            # repos mode — portfolio summary + optional individual repo report
            selected_repo_name = request.query_params.get("repo")
            summary = await run_in_threadpool(
                _build_repo_summary, db, current_user.id, days
            )
            repo_report_data = None
            if selected_repo_name:
                repo = repository_repo.find_by_full_name(db, selected_repo_name)
                if repo and (
                    repo.user_id is None or repo.user_id == current_user.id
                ):
                    now = datetime.now(_tz.utc)
                    repo_report_data = {
                        "repo_full_name": repo.full_name,
                        "kpi": repo_kpi(db, repo.id, days, now=now),
                        "recurring_issues": repo_recurring_issues(
                            db, repo.id, days, now=now
                        ),
                        "category_breakdown": repo_category_breakdown(
                            db, repo.id, days, now=now
                        ),
                        "ai_suggestions": repo_ai_suggestions(
                            db, repo.id, days, now=now
                        ),
                        "score_trend": repo_score_trend(
                            db, repo.id, days, now=now
                        ),
                    }
            return templates.TemplateResponse(
                request,
                _DASHBOARD_TEMPLATE,
                {
                    "current_user": current_user,
                    "mode": effective_mode,
                    "initial_mode": effective_mode,
                    "days": days,
                    "summary": summary,
                    "repo_report": repo_report_data,
                    "selected_repo": selected_repo_name,
                    "locale": locale_value,
                },
            )

        if effective_mode == "security":
            # Cycle 73 F2 — Code Scanning + Secret Scanning audit dashboard (read-only).
            # SQLAlchemy 2.x: session은 단일 스레드 순차 접근 시 다른 스레드에 전달 가능.
            # SQLAlchemy 2.x: session may be passed to another thread for sequential-only access.
            security = await run_in_threadpool(
                dashboard_service.dashboard_security, db, user_id=current_user.id
            )
            return templates.TemplateResponse(
                request,
                _DASHBOARD_TEMPLATE,
                {
                    "current_user": current_user,
                    "mode": "security",
                    "initial_mode": effective_mode,
                    "security": security,
                    "days": days,
                    "locale": locale_value,
                },
            )

        if effective_mode == "usage":
            # Cycle 79 PR 3b — SaaS Phase 1 본인 사용량 dashboard (read-only — user_id 직접 격리).
            # Cycle 79 PR 3b — SaaS Phase 1 own usage dashboard (read-only — user_id direct isolation).
            usage = await run_in_threadpool(
                dashboard_service.dashboard_usage, db, user_id=current_user.id, days=days
            )
            return templates.TemplateResponse(
                request,
                _DASHBOARD_TEMPLATE,
                {
                    "current_user": current_user,
                    "mode": "usage",
                    "initial_mode": effective_mode,
                    "usage": usage,
                    "days": days,
                    "locale": locale_value,
                },
            )

        if effective_mode == "insight":
            # Phase 3 PR 2 — Claude AI 4 카드 narrative (caching 적용) + PR 5 user_id 격리.
            # Phase 2-B 🅑 (사이클 74 PR-B) — DB 캐싱 1h TTL + ?refresh=1 강제 무효화
            # Phase 2-B 🅑 (Cycle 74 PR-B) — DB cache 1h TTL + ?refresh=1 forces invalidation.
            insight = await dashboard_service.insight_narrative(
                db, days=days, user_id=current_user.id, refresh=bool(refresh),
                language=locale_value,
            )
            return templates.TemplateResponse(
                request,
                _DASHBOARD_TEMPLATE,
                {
                    "current_user": current_user,
                    "mode": "insight",
                    "initial_mode": effective_mode,  # PR 4 — 클라이언트 JS data-initial-mode 신호
                    "insight": insight,
                    "days": days,
                    "locale": locale_value,
                },
            )

        # effective_mode == "overview" — 기존 동작 보존 + PR 5 user_id 격리
        # effective_mode == "overview" — preserves prior behavior + PR 5 user_id isolation
        _uid = current_user.id

        def _load_overview() -> tuple:
            # 7 sync DB 호출을 스레드 풀에서 일괄 실행 — 이벤트 루프 블로킹 방지.
            # Batch 7 sync DB calls in threadpool — prevents event loop blocking.
            kpi_ = dashboard_service.dashboard_kpi(db, days=days, user_id=_uid)
            trend_ = dashboard_service.dashboard_trend(db, days=days, user_id=_uid)
            freq_ = dashboard_service.frequent_issues_v2(db, days=days, n=5, user_id=_uid)
            am_ = dashboard_service.auto_merge_kpi(db, days=days, user_id=_uid)
            mf_ = dashboard_service.merge_failure_distribution(db, days=days, n=5, user_id=_uid)
            rc_ = dashboard_service.repo_insight_cards(db, days=days, user_id=_uid)
            fb_ = dashboard_service.feedback_status(db)
            return kpi_, trend_, freq_, am_, mf_, rc_, fb_

        # Phase 2 PR 1: Auto-merge KPI + 실패 분포.
        # 0031 — 리포별 인사이트 카드 섹션 (overview 모드 전용)
        # Phase 2 PR 2 (2026-05-02): feedback CTA — 운영 row=0 → 사용자 행동 유도.
        kpi, trend, frequent_issues, auto_merge, merge_failures, repo_cards, feedback = (
            await run_in_threadpool(_load_overview)
        )

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
            "repo_cards": repo_cards,
            "days": days,
            "locale": locale_value,
        },
    )


# ─── Legacy URL Redirects (Phase 1 PR 5) ───────────────────────────────────
# 폐기된 /insights, /insights/me 의 북마크 사용자 보호 — 영구 (301) 리다이렉트.
# Permanent redirect for users with bookmarks of the deprecated URLs.


def _redirect_to_dashboard(request: Request) -> RedirectResponse:
    """폐기 URL → 301 /dashboard (쿼리 파라미터 보존).

    Permanent (301) redirect to /dashboard, preserving query string.
    """
    qs = request.url.query
    target = f"/dashboard?{qs}" if qs else "/dashboard"
    return RedirectResponse(url=target, status_code=301)


@router.get("/insights")
def redirect_insights(request: Request) -> RedirectResponse:
    """GET /insights → 301 /dashboard."""
    return _redirect_to_dashboard(request)


@router.get("/insights/me")
def redirect_insights_me(request: Request) -> RedirectResponse:
    """GET /insights/me → 301 /dashboard."""
    return _redirect_to_dashboard(request)
