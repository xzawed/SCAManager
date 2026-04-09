"""Repository and config REST API endpoints (/api/repos/*)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.api.auth import require_api_key
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.config_manager.manager import upsert_repo_config, RepoConfigData

router = APIRouter(prefix="/api", dependencies=[require_api_key])


class RepoConfigUpdate(BaseModel):
    """Request body for PUT /api/repos/{repo}/config."""

    gate_mode: str = "disabled"
    auto_approve_threshold: int = 75
    auto_reject_threshold: int = 50
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    custom_webhook_url: str | None = None
    email_recipients: str | None = None
    auto_merge: bool = False


@router.get("/repos")
def list_repos():
    with SessionLocal() as db:
        repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
        return [
            {"id": r.id, "full_name": r.full_name,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in repos
        ]


@router.get("/repos/{repo_name:path}/analyses")
def list_repo_analyses(repo_name: str, skip: int = 0, limit: int = 20):
    with SessionLocal() as db:
        repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found")
        analyses = (
            db.query(Analysis)
            .filter(Analysis.repo_id == repo.id)
            .order_by(Analysis.created_at.desc())
            .offset(skip).limit(limit).all()
        )
        return [
            {"id": a.id, "commit_sha": a.commit_sha, "pr_number": a.pr_number,
             "score": a.score, "grade": a.grade,
             "created_at": a.created_at.isoformat() if a.created_at else None}
            for a in analyses
        ]


@router.put("/repos/{repo_name:path}/config")
def update_repo_config(repo_name: str, body: RepoConfigUpdate):
    with SessionLocal() as db:
        record = upsert_repo_config(db, RepoConfigData(
            repo_full_name=repo_name,
            gate_mode=body.gate_mode,
            auto_approve_threshold=body.auto_approve_threshold,
            auto_reject_threshold=body.auto_reject_threshold,
            notify_chat_id=body.notify_chat_id,
            n8n_webhook_url=body.n8n_webhook_url,
            discord_webhook_url=body.discord_webhook_url,
            slack_webhook_url=body.slack_webhook_url,
            custom_webhook_url=body.custom_webhook_url,
            email_recipients=body.email_recipients,
            auto_merge=body.auto_merge,
        ))
        return {
            "repo_full_name": record.repo_full_name,
            "gate_mode": record.gate_mode,
            "auto_approve_threshold": record.auto_approve_threshold,
            "auto_reject_threshold": record.auto_reject_threshold,
            "notify_chat_id": record.notify_chat_id,
            "n8n_webhook_url": record.n8n_webhook_url,
            "auto_merge": record.auto_merge,
        }
