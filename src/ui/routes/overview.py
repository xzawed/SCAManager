"""Overview 페이지 — `GET /` 전체 리포 현황 대시보드.
Overview page — `GET /` full repo status dashboard.

비인증 사용자에게는 랜딩 페이지를 보여준다.
Shows landing page to unauthenticated visitors.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func

from src.auth.session import CurrentUser, get_current_user
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.repositories import analysis_feedback_repo
from src.scorer.calculator import calculate_grade
from src.ui._helpers import get_locale, templates

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def overview(
    request: Request,
    current_user: Annotated[CurrentUser | None, Depends(get_current_user)],
):
    """전체 리포 현황 대시보드를 렌더링한다. 미인증 시 랜딩 페이지 반환.
    Renders repo dashboard. Returns landing page for unauthenticated visitors.
    """
    if current_user is None:
        return templates.TemplateResponse(request, "landing.html", {
            "locale": get_locale(request),
        })
    with SessionLocal() as db:
        repos = db.query(Repository).filter(
            (Repository.user_id == current_user.id) | (Repository.user_id.is_(None))
        ).order_by(Repository.created_at.desc()).all()
        repo_data = []
        if repos:
            repo_ids = [r.id for r in repos]

            count_map = dict(
                db.query(Analysis.repo_id, func.count(Analysis.id))  # pylint: disable=not-callable
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )
            avg_map = dict(
                db.query(Analysis.repo_id, func.avg(Analysis.score))  # pylint: disable=not-callable
                .filter(Analysis.repo_id.in_(repo_ids))
                .group_by(Analysis.repo_id)
                .all()
            )

            for r in repos:
                count = count_map.get(r.id, 0)
                avg = round(avg_map.get(r.id) or 0)
                repo_data.append({
                    "full_name": r.full_name,
                    "analysis_count": count,
                    "avg_score": avg,
                    "avg_grade": calculate_grade(avg) if count > 0 else None,
                })

        # Phase E.3-d — AI 점수 정합도 지표 (전역)
        calibration = analysis_feedback_repo.get_calibration_by_score_range(db)
    return templates.TemplateResponse(request, "overview.html", {
        "repos": repo_data,
        "current_user": current_user,
        "calibration": calibration,
        "locale": get_locale(request),
    })
