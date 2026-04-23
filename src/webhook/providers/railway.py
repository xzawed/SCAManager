"""Railway deploy-failure webhook provider — POST /webhooks/railway/{token}.

Railway 빌드 실패 이벤트를 수신해 GitHub Issue 를 자동 생성한다.
railway_api_token 이 설정되어 있으면 GraphQL 로 로그 tail 을 조회해 포함.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from src.config import settings
from src.crypto import decrypt_token
from src.database import SessionLocal
from src.models.repository import Repository
from src.models.user import User as UserModel
from src.notifier.railway_issue import create_deploy_failure_issue
from src.railway_client.logs import RailwayLogFetchError, fetch_deployment_logs
from src.railway_client.models import RailwayDeployEvent
from src.railway_client.webhook import parse_railway_payload
from src.repositories import repo_config_repo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/railway/{token}")
async def railway_webhook(
    token: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    """Railway 빌드 실패 Webhook 수신 → BackgroundTask 로 GitHub Issue 생성."""
    try:
        body = await request.json()
    except Exception:  # pylint: disable=broad-except
        body = {}

    with SessionLocal() as db:
        config = repo_config_repo.find_by_railway_webhook_token(db, token)
        if config is None:
            raise HTTPException(status_code=404, detail="Not Found")

        deploy_alerts = config.railway_deploy_alerts
        # 세션 종료 전 필요 값 추출 (lazy-load 금지 — CLAUDE.md 규약)
        repo_full_name = config.repo_full_name
        decrypted_api_token = (
            decrypt_token(config.railway_api_token) if config.railway_api_token else None
        )

        repo = db.query(Repository).filter(
            Repository.full_name == repo_full_name
        ).first()
        github_token = settings.github_token or ""
        if repo and repo.user_id:
            user = db.query(UserModel).filter(UserModel.id == repo.user_id).first()
            if user:
                github_token = user.plaintext_token or github_token

    if not deploy_alerts:
        return {"status": "ignored"}

    event = parse_railway_payload(body)
    if event is None:
        return {"status": "ignored"}

    background_tasks.add_task(
        _handle_railway_deploy_failure,
        repo_full_name=repo_full_name,
        event=event,
        decrypted_api_token=decrypted_api_token,
        github_token=github_token,
    )
    return JSONResponse({"status": "accepted"}, status_code=202)


async def _handle_railway_deploy_failure(
    *,
    repo_full_name: str,
    event: RailwayDeployEvent,
    decrypted_api_token: str | None,
    github_token: str,
) -> None:
    """Railway 빌드 실패 이벤트를 처리하고 GitHub Issue 를 생성한다."""
    logs_tail: str | None = None
    if decrypted_api_token:
        try:
            logs_tail = await fetch_deployment_logs(decrypted_api_token, event.deployment_id)
        except RailwayLogFetchError as exc:
            logger.warning("Railway 로그 조회 실패 (%s): %s", event.deployment_id, exc)
            logs_tail = f"로그 조회 실패: {exc}"

    await create_deploy_failure_issue(
        github_token=github_token,
        repo_full_name=repo_full_name,
        event=event,
        logs_tail=logs_tail,
    )
