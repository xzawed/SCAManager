"""Team/Multi-repo Insights UI 라우트 — 멀티 리포 비교 및 개인 추세 대시보드.
Team/multi-repo insights UI routes — multi-repo comparison and personal trend dashboard.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.models.repository import Repository
from src.services import analytics_service
from src.ui._helpers import templates

router = APIRouter()


@router.get("/insights", response_class=HTMLResponse)
def insights_comparison(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    repos: str = "",
    days: int = 30,
):
    """멀티 리포 평균 점수 비교 페이지.
    Multi-repo average score comparison page.
    """
    full_names = [r.strip() for r in repos.split(",") if r.strip()] if repos else []

    with SessionLocal() as db:
        # 사용자 접근 가능한 모든 리포 목록 (리포 셀렉터 용도)
        # All accessible repos for the repo selector
        all_repos = (
            db.query(Repository)
            .filter(
                (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))
            )
            .order_by(Repository.full_name.asc())
            .all()
        )

        # 선택된 리포의 full_name → repo_id 매핑
        # Resolve selected full_names to repo_ids
        comparison: list[dict] = []
        if full_names:
            selected_repos = (
                db.query(Repository)
                .filter(Repository.full_name.in_(full_names))
                .all()
            )
            id_to_name = {r.id: r.full_name for r in selected_repos}
            repo_ids = list(id_to_name.keys())
            raw = analytics_service.repo_comparison(db, repo_ids, days)
            comparison = [
                {
                    "repo_id": item["repo_id"],
                    "full_name": id_to_name.get(item["repo_id"], ""),
                    "avg_score": item["avg_score"],
                    "count": item["count"],
                }
                for item in raw
            ]

    return templates.TemplateResponse(
        request,
        "insights.html",
        {
            "current_user": current_user,
            "comparison": comparison,
            "repos": full_names,
            "days": days,
            "all_repos": all_repos,
        },
    )


@router.get("/insights/me", response_class=HTMLResponse)
def insights_me(
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    days: int = 30,
):
    """개인 개발자 점수 추세 페이지.
    Personal developer score trend page.
    """
    with SessionLocal() as db:
        trend = analytics_service.author_trend(db, current_user.github_login, days)

    return templates.TemplateResponse(
        request,
        "insights_me.html",
        {
            "current_user": current_user,
            "trend": trend,
            "days": days,
        },
    )
