"""Repository and config REST API endpoints (/api/repos/*)."""
from typing import Annotated, Literal
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from src.config import settings
from src.middleware.rate_limiter import limiter, RATE_LIMIT_API, RATE_LIMIT_HEAVY
from src.api.auth import require_api_key
from src.api.deps import get_repo_or_404
from src.shared.ssrf import is_safe_webhook_url
from src.constants import (
    GATE_DEFAULT_APPROVE_THRESHOLD,
    GATE_DEFAULT_REJECT_THRESHOLD,
    GATE_DEFAULT_MERGE_THRESHOLD,
)
# require_api_key(글로벌 키) 시스템 엔드포인트 — 사용자 세션 없이 cross-tenant 전체 데이터 조회.
# Phase 4 비-BYPASSRLS app role 전환 시 RLS 가 owned 행을 은닉/차단하므로 worker 세션(BYPASSRLS) 경유.
# DATABASE_URL_WORKER 미설정 시 WorkerSessionLocal is SessionLocal — 현행 동작 동일.
# Global-API-key system endpoints — cross-tenant reads with no user session. After the Phase 4
# non-BYPASSRLS app-role switch, RLS would hide/block owned rows, so route via the worker (BYPASSRLS)
# session. With DATABASE_URL_WORKER unset, WorkerSessionLocal is SessionLocal (behavior unchanged).
from src.database import WorkerSessionLocal as SessionLocal
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
    approve_threshold: int = Field(GATE_DEFAULT_APPROVE_THRESHOLD, ge=0, le=100)
    reject_threshold: int = Field(GATE_DEFAULT_REJECT_THRESHOLD, ge=0, le=100)
    notify_chat_id: str | None = None
    n8n_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None
    custom_webhook_url: str | None = None
    email_recipients: str | None = None
    auto_merge: bool = False
    merge_threshold: int = Field(GATE_DEFAULT_MERGE_THRESHOLD, ge=0, le=100)
    commit_comment: bool = False
    create_issue: bool = False
    railway_deploy_alerts: bool = False
    auto_merge_issue_on_failure: bool = False
    # Phase 1 PR-1c (사이클 84) — 다국어 지원 리포별 알림 언어 override
    # NULL = 사용자 preferred_language fallback (Phase 3 PR-9~11 알림 채널 영역)
    notification_language: str | None = None
    # 리포별 Claude 코드리뷰 모델 override (Alembic 0032)
    # NULL = settings.claude_review_model 전역 기본값 사용
    review_model: str | None = None
    # per-repo 비활성화 도구 목록 — JSON 배열, 기본값 빈 배열 (Alembic 0035)
    # Per-repo disabled analyzer names — JSON array, defaults to empty list (Alembic 0035)
    disabled_tools: list = Field(default_factory=list)
    # leaderboard_opt_in 폐기 (그룹 60 사용자 결정 정정 — alembic 0025)

    @field_validator("notification_language")
    @classmethod
    def validate_notification_language(cls, v):
        """notification_language SUPPORTED_LOCALES 검증 (None/빈값 허용 — preferred_language fallback).

        Validate notification_language against SUPPORTED_LOCALES.
        None/empty is allowed (intended fallback to user preferred_language).
        """
        if v is None or v == "":
            # None/빈값 = fallback 의도, 허용 (조용한 영문 fallback 아님 — 정상 설계)
            # None/empty = intended fallback, allowed
            return None
        v = v.strip().lower()
        if v == "":
            return None
        supported = {lang.strip() for lang in settings.supported_locales.split(",")}
        if v not in supported:
            raise ValueError(
                f"notification_language '{v}' not in SUPPORTED_LOCALES "
                f"({settings.supported_locales})"
            )
        return v

    @field_validator(
        "n8n_webhook_url", "discord_webhook_url", "slack_webhook_url", "custom_webhook_url"
    )
    @classmethod
    def validate_webhook_url(cls, v):
        """저장-시 SSRF 검증 — UI 폼(settings._validate_webhook_urls)과 동일 단일 출처.

        send-time(`validate_external_url`)이 최종 차단하나, REST 저장 경로도 https + 비-내부 호스트를
        조기 거부해 폼과 대칭(저장됐으나 발송 안 되는 혼란·방어 심층). None/빈값/도메인명은 허용.
        Storage-time SSRF check — same single source as the UI form. Send-time validation is the final
        control, but the REST path rejects non-https / internal-host URLs early (symmetry + defense-in-depth).
        """
        if v and not is_safe_webhook_url(v):
            raise ValueError(
                "webhook URL must be https and not point to an internal/metadata host (SSRF guard)"
            )
        return v

    @model_validator(mode="after")
    def validate_thresholds(self) -> "RepoConfigUpdate":
        """approve_threshold가 reject_threshold 이상인지 검증한다."""
        if self.approve_threshold < self.reject_threshold:
            # API 422 응답 — 형제 validator(notification_language)와 동일하게 영문 고정
            # API 422 response — kept English, consistent with the sibling validator
            raise ValueError(
                f"approve_threshold({self.approve_threshold}) must be >= "
                f"reject_threshold({self.reject_threshold})"
            )
        return self


@router.get("/repos")
@limiter.limit(RATE_LIMIT_API)
def list_repos(request: Request):  # pylint: disable=unused-argument
    """등록된 전체 리포지토리 목록을 반환한다."""
    with SessionLocal() as db:
        repos = db.query(Repository).order_by(Repository.created_at.desc()).all()
        return [
            {"id": r.id, "full_name": r.full_name,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in repos
        ]


@router.get("/repos/{repo_name:path}/analyses")
@limiter.limit(RATE_LIMIT_API)
def list_repo_analyses(
    request: Request,
    repo_name: str,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
):  # pylint: disable=unused-argument
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
@limiter.limit(RATE_LIMIT_HEAVY)
def update_repo_config(request: Request, repo_name: str, body: RepoConfigUpdate):  # pylint: disable=unused-argument
    """리포지토리 Gate·알림 설정을 업데이트한다."""
    with SessionLocal() as db:
        record = upsert_repo_config(db, RepoConfigData(
            repo_full_name=repo_name,
            **body.model_dump(),
        ))
        return {"repo_full_name": record.repo_full_name, **body.model_dump()}


@router.delete("/repos/{repo_name:path}")
@limiter.limit(RATE_LIMIT_HEAVY)
def delete_repo_api(request: Request, repo_name: str):  # pylint: disable=unused-argument
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
