"""Repository and config REST API endpoints (/api/repos/*)."""
from typing import Literal
from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator
from src.api.auth import require_api_key
from src.api.deps import get_repo_or_404
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.models.gate_decision import GateDecision
from src.repositories import repo_config_repo
from src.config_manager.manager import upsert_repo_config, RepoConfigData

router = APIRouter(prefix="/api", dependencies=[require_api_key])


class RepoConfigUpdate(BaseModel):
    """Request body for PUT /api/repos/{repo}/config."""

    pr_review_comment: bool = True
    approve_mode: Literal["disabled", "auto", "semi-auto"] = "disabled"
    approve_threshold: int = Field(75, ge=0, le=100)
    reject_threshold: int = Field(50, ge=0, le=100)
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    custom_webhook_url: str | None = None
    email_recipients: str | None = None
    auto_merge: bool = False
    merge_threshold: int = Field(75, ge=0, le=100)
    commit_comment: bool = False
    create_issue: bool = False
    railway_deploy_alerts: bool = False
    auto_merge_issue_on_failure: bool = False
    # leaderboard_opt_in 폐기 (그룹 60 사용자 결정 정정 — alembic 0025)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "RepoConfigUpdate":
        """approve_threshold가 reject_threshold 이상인지 검증한다."""
        if self.approve_threshold < self.reject_threshold:
            raise ValueError(
                f"approve_threshold({self.approve_threshold})는 "
                f"reject_threshold({self.reject_threshold}) 이상이어야 합니다"
            )
        return self


@router.get("/repos")
def list_repos():
    """등록된 전체 리포지토리 목록을 반환한다."""
    with SessionLocal() as db:
        repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
        return [
            {"id": r.id, "full_name": r.full_name,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in repos
        ]


@router.get("/repos/{repo_name:path}/analyses")
def list_repo_analyses(repo_name: str, skip: int = 0, limit: int = 20):
    """리포지토리 분석 이력 목록을 반환한다."""
    with SessionLocal() as db:
        repo = get_repo_or_404(repo_name, db)
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
    """리포지토리 Gate·알림 설정을 업데이트한다."""
    with SessionLocal() as db:
        record = upsert_repo_config(db, RepoConfigData(
            repo_full_name=repo_name,
            **body.model_dump(),
        ))
        return {"repo_full_name": record.repo_full_name, **body.model_dump()}


@router.delete("/repos/{repo_name:path}")
def delete_repo_api(repo_name: str):
    """리포지토리와 모든 연관 데이터(Analysis, GateDecision, RepoConfig)를 삭제한다.

    API 모드는 사용자 OAuth 토큰이 없으므로 GitHub Webhook은 자동 삭제하지 않는다.
    응답에 `webhook_id`를 포함해 호출자가 직접 정리할 수 있게 한다.
    """
    with SessionLocal() as db:
        repo = get_repo_or_404(repo_name, db)
        webhook_id = repo.webhook_id
        full_name = repo.full_name

        analysis_ids = [
            row.id for row in db.query(Analysis.id).filter(Analysis.repo_id == repo.id).all()
        ]
        if analysis_ids:
            db.query(GateDecision).filter(
                GateDecision.analysis_id.in_(analysis_ids)
            ).delete(synchronize_session=False)
        db.query(Analysis).filter(Analysis.repo_id == repo.id).delete(synchronize_session=False)
        repo_config_repo.delete_by_full_name(db, full_name)
        db.delete(repo)
        db.commit()

    return {"deleted": True, "repo_full_name": full_name, "webhook_id": webhook_id}
