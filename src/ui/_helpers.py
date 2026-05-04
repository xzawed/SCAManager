"""UI 공용 헬퍼 — templates, logger, 접근 제어, delete cascade.

각 `src/ui/routes/*.py` 가 본 모듈의 함수·상수를 import 해서 사용한다.
mock 전략: helper 자체를 patch 하려면 `src.ui._helpers.<name>` 경로 사용.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.auth.session import CurrentUser
from src.config import settings
from src.github_client.repos import delete_webhook
from src.models.analysis import Analysis
from src.models.gate_decision import GateDecision
from src.models.repository import Repository
from src.repositories import repo_config_repo, repository_repo
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger("src.ui")
templates = Jinja2Templates(directory="src/templates")

# GitHub Webhook 수신 경로 — add_repo + settings 에서 사용 (상수화)
GITHUB_WEBHOOK_PATH = "/webhooks/github"


def webhook_base_url(request: Request) -> str:
    """APP_BASE_URL 설정 시 해당 URL 우선 사용 (Railway HTTPS 보장)."""
    if settings.app_base_url:
        return settings.app_base_url.rstrip("/")
    return str(request.base_url).rstrip("/")


def get_accessible_repo(db: Session, repo_name: str, current_user: CurrentUser) -> Repository:
    """로그인 사용자가 접근 가능한 리포를 반환. 없거나 권한 없으면 404."""
    repo = repository_repo.find_by_full_name(db, repo_name)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.user_id is not None and repo.user_id != current_user.id:
        raise HTTPException(status_code=404)
    return repo


async def delete_repo_cascade(db: Session, repo: Repository, github_token: str) -> None:
    """리포 + 연관 데이터(Webhook, GateDecision, Analysis, RepoConfig)를 모두 삭제한다.

    Webhook 삭제는 best-effort — GitHub API 실패 시에도 DB 정리는 계속 진행된다.
    """
    if repo.webhook_id:
        try:
            await delete_webhook(github_token, repo.full_name, repo.webhook_id)
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-except
            # best-effort: GitHub API 실패 시 운영 관측 위해 logger.warning (Sentry 송출)
            # best-effort: log warning on GitHub API failure for observability (Sentry)
            logger.warning(
                "delete_repo_cascade: webhook delete failed for %s: %s",
                sanitize_for_log(repo.full_name), type(exc).__name__,
            )

    analysis_ids = [
        row.id for row in db.query(Analysis.id).filter(Analysis.repo_id == repo.id).all()
    ]
    if analysis_ids:
        db.query(GateDecision).filter(
            GateDecision.analysis_id.in_(analysis_ids)
        ).delete(synchronize_session=False)

    db.query(Analysis).filter(Analysis.repo_id == repo.id).delete(synchronize_session=False)
    repo_config_repo.delete_by_full_name(db, repo.full_name)
    db.delete(repo)
    db.commit()
