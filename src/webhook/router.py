"""Webhook endpoints — POST /webhooks/github and POST /api/webhook/telegram."""
import hashlib
import hmac
import json
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Header
from sqlalchemy.exc import SQLAlchemyError
from src.config import settings
from src.webhook.validator import verify_github_signature
from src.worker.pipeline import run_analysis_pipeline
from src.gate.engine import _save_gate_decision
from src.gate.github_review import post_github_review, merge_pr
from src.config_manager.manager import get_repo_config
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.database import SessionLocal
from src.constants import HANDLED_EVENTS, PR_HANDLED_ACTIONS
from src.notifier.n8n import notify_n8n_issue

logger = logging.getLogger(__name__)

router = APIRouter()

HANDLED_PR_ACTIONS = PR_HANDLED_ACTIONS  # 하위 호환 별칭


@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    payload = await request.body()

    # payload에서 리포 이름 파싱 (per-repo 시크릿 조회용)
    full_name = ""
    try:
        data = json.loads(payload)
        full_name = data.get("repository", {}).get("full_name", "")
    except (json.JSONDecodeError, AttributeError):
        data = {}

    # 리포별 시크릿 조회 → 없으면 전역 시크릿 fallback
    secret = settings.github_webhook_secret
    if full_name:
        try:
            with SessionLocal() as db:
                repo = db.query(Repository).filter(
                    Repository.full_name == full_name
                ).first()
                if repo and repo.webhook_secret:
                    secret = repo.webhook_secret
        except Exception as exc:  # noqa: BLE001
            logger.warning("Per-repo webhook secret lookup failed, using global secret: %s", exc)

    if not secret:
        raise HTTPException(status_code=401, detail="Webhook secret not configured")
    if not verify_github_signature(payload, x_hub_signature_256, secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if not data:
        return {"status": "ignored"}

    if x_github_event not in HANDLED_EVENTS:
        return {"status": "ignored"}

    if x_github_event == "pull_request":
        action = data.get("action")
        if action not in HANDLED_PR_ACTIONS:
            return {"status": "ignored"}

    if x_github_event == "issues":
        return await _handle_issues_event(data, background_tasks)

    background_tasks.add_task(run_analysis_pipeline, x_github_event, data)
    return {"status": "accepted"}


async def _handle_issues_event(data: dict, background_tasks: BackgroundTasks) -> dict:
    """GitHub Issues 이벤트를 n8n으로 릴레이한다."""
    repo_name = data.get("repository", {}).get("full_name", "")
    if not repo_name:
        return {"status": "ignored"}

    n8n_url = None
    try:
        with SessionLocal() as db:
            config = get_repo_config(db, repo_name)
            n8n_url = config.n8n_webhook_url
    except Exception as exc:  # noqa: BLE001
        logger.warning("issues relay: repo config lookup failed for %s: %s", repo_name, exc)

    if not n8n_url:
        return {"status": "ignored"}

    action = data.get("action", "")
    issue = data.get("issue", {})
    sender = data.get("sender", {})
    background_tasks.add_task(
        notify_n8n_issue,
        webhook_url=n8n_url,
        repo_full_name=repo_name,
        action=action,
        issue=issue,
        sender=sender,
        n8n_secret=settings.n8n_webhook_secret,
    )
    return {"status": "accepted"}


async def handle_gate_callback(
    analysis_id: int,
    decision: str,
    decided_by: str,
) -> None:
    with SessionLocal() as db:
        try:
            analysis = db.query(Analysis).filter_by(id=analysis_id).first()
            if not analysis:
                logger.warning("handle_gate_callback: analysis %d not found", analysis_id)
                return
            repo = db.query(Repository).filter_by(id=analysis.repo_id).first()
            if not repo:
                return
            github_token = (
                repo.owner.plaintext_token
                if repo.owner and repo.owner.plaintext_token
                else settings.github_token
            )
            body = f"{'✅ 승인' if decision == 'approve' else '❌ 반려'} by @{decided_by}"
            await post_github_review(
                github_token, repo.full_name,
                analysis.pr_number, decision, body,
            )
            _save_gate_decision(db, analysis_id, decision, "manual", decided_by)
            config = get_repo_config(db, repo.full_name)
            result_dict = analysis.result if isinstance(analysis.result, dict) else {}
            score = result_dict.get("score", analysis.score or 0)
            if config.auto_merge and score >= config.merge_threshold:
                merged = await merge_pr(github_token, repo.full_name, analysis.pr_number)
                if merged:
                    logger.info("PR #%d manual-approved+auto-merged: %s",
                                analysis.pr_number, repo.full_name)
        except (httpx.HTTPError, KeyError, ValueError, SQLAlchemyError) as exc:
            logger.error("Gate callback failed: %s", exc)


@router.post("/api/webhook/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Telegram 게이트 콜백 수신 엔드포인트.

    TELEGRAM_WEBHOOK_SECRET 설정 시 X-Telegram-Bot-Api-Secret-Token 헤더를 검증한다.
    """
    if settings.telegram_webhook_secret:
        provided = x_telegram_bot_api_secret_token or ""
        if not hmac.compare_digest(provided, settings.telegram_webhook_secret):
            logger.warning("Telegram webhook: invalid or missing secret token")
            return {"status": "ok"}

    payload = await request.json()
    callback_query = payload.get("callback_query")
    if not callback_query:
        return {"status": "ok"}
    data = callback_query.get("data", "")
    if not data.startswith("gate:"):
        return {"status": "ok"}
    parts = data.split(":")
    if len(parts) != 4:
        return {"status": "ok"}
    _, decision, analysis_id_str, callback_token = parts
    if decision not in ("approve", "reject"):
        return {"status": "ok"}
    try:
        analysis_id = int(analysis_id_str)
    except ValueError:
        return {"status": "ok"}
    expected = hmac.new(
        settings.telegram_bot_token.encode(),
        str(analysis_id).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()[:32]
    if not hmac.compare_digest(expected, callback_token):
        logger.warning("Telegram gate callback: invalid token for analysis_id=%d", analysis_id)
        return {"status": "ok"}
    from_data = callback_query.get("from", {})
    user_id = from_data.get("id", "unknown")
    username = from_data.get("username", "")
    decided_by = f"{username}(id:{user_id})" if username else f"id:{user_id}"
    background_tasks.add_task(
        handle_gate_callback,
        analysis_id=analysis_id,
        decision=decision,
        decided_by=decided_by,
    )
    return {"status": "ok"}
