"""리포 분석 이력 + 분석 상세 페이지 — catch-all `/repos/{name}` 는 마지막에 include."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from src.auth.session import CurrentUser, require_login
from src.database import SessionLocal
from src.models.analysis import Analysis
from src.ui._helpers import get_accessible_repo, templates

router = APIRouter()


@router.get("/repos/{repo_name:path}/analyses/{analysis_id}", response_class=HTMLResponse)
def analysis_detail(
    request: Request, repo_name: str, analysis_id: int,
    current_user: Annotated[CurrentUser, Depends(require_login)],
):
    """분석 상세 페이지(AI 리뷰·점수·피드백)를 렌더링한다."""
    with SessionLocal() as db:
        repo = get_accessible_repo(db, repo_name, current_user)
        analysis = db.query(Analysis).filter(
            Analysis.id == analysis_id, Analysis.repo_id == repo.id
        ).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        result = analysis.result or {}
        source = result.get("source") or ("pr" if analysis.pr_number else "push")
        data = {
            "id": analysis.id,
            "commit_sha": analysis.commit_sha,
            "commit_message": analysis.commit_message,
            "pr_number": analysis.pr_number,
            "score": analysis.score,
            "grade": analysis.grade,
            "result": result,
            "source": source,
            "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        }
        siblings = (db.query(Analysis.id, Analysis.score, Analysis.created_at)
                    .filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(30).all())
        trend_data = [
            {"id": s.id, "score": s.score,
             "label": s.created_at.strftime("%m/%d") if s.created_at else ""}
            for s in reversed(siblings)
        ]
        prev_id = (db.query(Analysis.id)
                   .filter(Analysis.repo_id == repo.id, Analysis.id < analysis_id)
                   .order_by(Analysis.id.desc()).limit(1).scalar())
        next_id = (db.query(Analysis.id)
                   .filter(Analysis.repo_id == repo.id, Analysis.id > analysis_id)
                   .order_by(Analysis.id.asc()).limit(1).scalar())
    return templates.TemplateResponse(request, "analysis_detail.html", {
        "repo_name": repo_name, "analysis": data, "current_user": current_user,
        "trend_data": trend_data, "prev_id": prev_id, "next_id": next_id,
    })


@router.get("/repos/{repo_name:path}", response_class=HTMLResponse)
def repo_detail(  # pylint: disable=too-many-positional-arguments
    request: Request,
    repo_name: str,
    current_user: Annotated[CurrentUser, Depends(require_login)],
    hook_installed: int = 0,
):
    """리포 분석 이력 및 점수 차트 페이지를 렌더링한다."""
    with SessionLocal() as db:
        repo = get_accessible_repo(db, repo_name, current_user)
        analyses = (db.query(Analysis).filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(100).all())
        analyses_data = [
            {"id": a.id, "commit_sha": a.commit_sha, "pr_number": a.pr_number,
             "commit_message": a.commit_message,
             "score": a.score, "grade": a.grade,
             "source": (a.result or {}).get("source") or ("pr" if a.pr_number else "push"),
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in analyses
        ]
        rev = list(reversed(analyses_data))
    return templates.TemplateResponse(request, "repo_detail.html", {
        "repo_name": repo_name, "analyses": analyses_data,
        "chart_labels": [a["created_at"][:10] if a["created_at"] else "" for a in rev],
        "chart_scores": [a["score"] for a in rev],
        "hook_installed": bool(hook_installed),
        "current_user": current_user,
    })
