"""Railway deploy-failure webhook provider — POST /webhooks/railway/{token}.

Railway 빌드 실패 이벤트를 수신해 GitHub Issue 를 자동 생성한다.
railway_api_token 이 설정되어 있으면 GraphQL 로 로그 tail 을 조회해 포함.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse

from src.config import settings
from src.shared.secure_compare import secure_str_compare
from src.crypto import decrypt_token
from src.database import WorkerSessionLocal as SessionLocal
from src.models.user import User as UserModel
from src.notifier.railway_issue import create_deploy_failure_issue
from src.railway_client.logs import RailwayLogFetchError, fetch_deployment_logs
from src.railway_client.models import RailwayDeployEvent
from src.railway_client.webhook import parse_railway_payload
from src.repositories import repo_config_repo, repository_repo

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/railway/{token}", responses={404: {"description": "Token not found"}})
async def railway_webhook(  # pylint: disable=too-many-locals
    # 사이클 153 — 알림 언어(language) 해소 변수 추가로 16개 (시그니처 확장, 헬퍼 추출 시 응집 깨짐)
    # Cycle 153 — language resolution var added (signature extension; extracting a helper breaks cohesion)
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
        # SQL 동등 비교 후 constant-time 재검증 — timing oracle 방지 (hook.py:62 패턴과 동일)
        # Re-verify with constant-time comparison after SQL lookup to prevent timing oracle
        token_match = config is not None and secure_str_compare(
            config.railway_webhook_token, token
        )
        if not token_match:
            raise HTTPException(status_code=404, detail="Not Found")

        deploy_alerts = config.railway_deploy_alerts
        # 세션 종료 전 필요 값 추출 (lazy-load 금지 — CLAUDE.md 규약)
        repo_full_name = config.repo_full_name
        decrypted_api_token = (
            decrypt_token(config.railway_api_token) if config.railway_api_token else None
        )

        repo = repository_repo.find_by_full_name(db, repo_full_name)
        github_token = settings.github_token or ""
        if repo and repo.user_id:
            user = db.query(UserModel).filter(UserModel.id == repo.user_id).first()
            if user:
                github_token = user.plaintext_token or github_token

        # 세션 종료 전 알림 언어 해소 — Issue 제목/본문 i18n (사이클 153)
        # Resolve notification language before session closes — Issue title/body i18n
        from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        language = resolve_notification_language(db, config=config)

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
        language=language,
    )
    return JSONResponse({"status": "accepted"}, status_code=202)


async def _handle_railway_deploy_failure(
    *,
    repo_full_name: str,
    event: RailwayDeployEvent,
    decrypted_api_token: str | None,
    github_token: str,
    language: str = "ko",
) -> None:
    """Railway 빌드 실패 이벤트를 처리하고 GitHub Issue 를 생성한다.
    language: repo 소유자 알림 언어 (Issue 제목/본문 i18n)."""
    logs_tail: str | None = None
    if decrypted_api_token:
        try:
            logs_tail = await fetch_deployment_logs(decrypted_api_token, event.deployment_id)
        except RailwayLogFetchError as exc:
            # exc 상세는 운영자 로그에만 남기고, Issue 본문은 None 유지 →
            # railway_issue 가 i18n 키(notifier.railway.log_fetch_failed)로 대체 (사이클 154 P2)
            # Keep exc detail in operator logs only; leave body None so railway_issue
            # substitutes the i18n key (avoids leaking hardcoded Korean into the Issue)
            logger.warning("Railway 로그 조회 실패 (%s): %s", event.deployment_id, exc)
            logs_tail = None

    await create_deploy_failure_issue(
        github_token=github_token,
        repo_full_name=repo_full_name,
        language=language,
        event=event,
        logs_tail=logs_tail,
    )
