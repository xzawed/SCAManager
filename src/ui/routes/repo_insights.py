"""리포별 코드 인사이트 라우트 — GET /repos/{name}/insights.

Repository code insights route — GET /repos/{name}/insights.
"""
from __future__ import annotations

import logging
from typing import Annotated, Generator

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser, require_login
from src.config import settings
from src.database import SessionLocal
from src.models.repository import Repository
from src.services.repo_insight_service import (
    repo_ai_suggestions,
    repo_category_breakdown,
    repo_insight_narrative,
    repo_kpi,
    repo_problem_files,
    repo_recurring_issues,
)
from src.shared.log_safety import sanitize_for_log
from src.ui._helpers import get_locale, templates

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db() -> Generator[Session, None, None]:
    """DB 세션 의존성 — 테스트에서 override 가능.

    DB session dependency — overrideable in tests.
    """
    with SessionLocal() as db:
        yield db


def _find_repo(db: Session, repo_name: str, user_id: int):
    """사용자 접근 가능한 리포 조회 — 없거나 권한 없으면 None.

    Find user-accessible repo — returns None if not found or unauthorized.
    """
    repo = db.scalar(
        select(Repository).where(Repository.full_name == repo_name)
    )
    if repo is None:
        return None
    if repo.user_id is not None and repo.user_id != user_id:
        return None
    return repo


@router.get("/repos/{repo_name:path}/insights", response_class=HTMLResponse)
async def repo_insights(  # pylint: disable=too-many-positional-arguments
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    db: Annotated[Session, Depends(_get_db)],
    days: int = Query(default=30, ge=1, le=365),
    refresh: int = 0,
) -> HTMLResponse:
    """리포별 코드 인사이트 페이지.

    Per-repository code insights page.
    """
    logger.info(
        "repo_insights user_id=%d repo=%s days=%s",
        current_user.id,
        sanitize_for_log(repo_name),
        sanitize_for_log(str(days), max_len=5),
    )

    repo = _find_repo(db, repo_name, current_user.id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    kpi = repo_kpi(db, repo.id, days)
    recurring = repo_recurring_issues(db, repo.id, days)
    problem_files = repo_problem_files(db, repo.id, days)
    ai_suggestions = repo_ai_suggestions(db, repo.id, days)
    breakdown = repo_category_breakdown(db, repo.id, days)

    # AI 내러티브 — API 키 있을 때만
    # AI narrative — only when API key is configured
    narrative: dict | None = None
    if settings.anthropic_api_key:
        narrative = await repo_insight_narrative(
            db,
            repo.id,
            days,
            repo_full_name=repo.full_name,
            kpi=kpi,
            recurring=recurring,
            refresh=bool(refresh),
            user_id=current_user.id,
            language=get_locale(request),
        )
        if narrative and narrative.get("status") != "success":
            narrative = None

    return templates.TemplateResponse(
        request,
        "repo_insights.html",
        {
            "current_user": current_user,
            "repo": repo,
            "days": days,
            "kpi": kpi,
            "recurring_issues": recurring,
            "problem_files": problem_files,
            "ai_suggestions": ai_suggestions,
            "breakdown": breakdown,
            "narrative": narrative,
            "locale": get_locale(request),
        },
    )
