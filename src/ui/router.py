from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.models.user import User
from src.auth.session import require_login
from src.config_manager.manager import get_repo_config, upsert_repo_config, RepoConfigData

templates = Jinja2Templates(directory="src/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def overview(request: Request, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repos = db.query(Repository).filter(
            Repository.user_id == current_user.id
        ).order_by(Repository.created_at.desc()).all()
        repo_data = []
        for r in repos:
            latest = (db.query(Analysis).filter(Analysis.repo_id == r.id)
                      .order_by(Analysis.created_at.desc()).first())
            count = db.query(Analysis).filter(Analysis.repo_id == r.id).count()
            repo_data.append({
                "full_name": r.full_name,
                "analysis_count": count,
                "latest_score": latest.score if latest else None,
                "latest_grade": latest.grade if latest else None,
            })
    return templates.TemplateResponse(request, "overview.html", {
        "repos": repo_data,
        "current_user": current_user,
    })


@router.get("/repos/{repo_name:path}/settings", response_class=HTMLResponse)
def repo_settings(request: Request, repo_name: str, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=404)
        config = get_repo_config(db, repo_name)
    return templates.TemplateResponse(request, "settings.html", {
        "repo_name": repo_name, "config": config,
    })


@router.post("/repos/{repo_name:path}/settings")
async def update_repo_settings(
    request: Request,
    repo_name: str,
    current_user: User = Depends(require_login),  # pylint: disable=unused-argument
):
    form = await request.form()
    with SessionLocal() as db:
        upsert_repo_config(db, RepoConfigData(
            repo_full_name=repo_name,
            gate_mode=form.get("gate_mode", "disabled"),
            auto_approve_threshold=int(form.get("auto_approve_threshold", 75)),
            auto_reject_threshold=int(form.get("auto_reject_threshold", 50)),
            notify_chat_id=form.get("notify_chat_id") or None,
            n8n_webhook_url=form.get("n8n_webhook_url", ""),
            auto_merge=form.get("auto_merge") == "on",
        ))
    return RedirectResponse(url=f"/repos/{repo_name}/settings", status_code=303)


@router.get("/repos/{repo_name:path}", response_class=HTMLResponse)
def repo_detail(request: Request, repo_name: str, current_user: User = Depends(require_login)):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        if repo.user_id is not None and repo.user_id != current_user.id:
            raise HTTPException(status_code=404)
        analyses = (db.query(Analysis).filter(Analysis.repo_id == repo.id)
                    .order_by(Analysis.created_at.desc()).limit(30).all())
        analyses_data = [
            {"commit_sha": a.commit_sha, "pr_number": a.pr_number,
             "score": a.score, "grade": a.grade,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in analyses
        ]
        rev = list(reversed(analyses_data))
    return templates.TemplateResponse(request, "repo_detail.html", {
        "repo_name": repo_name, "analyses": analyses_data,
        "chart_labels": [a["created_at"][:10] if a["created_at"] else "" for a in rev],
        "chart_scores": [a["score"] for a in rev],
    })
