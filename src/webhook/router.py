import json
import logging
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Header
from src.config import settings
from src.webhook.validator import verify_github_signature
from src.worker.pipeline import run_analysis_pipeline
from src.gate.engine import _save_gate_decision
from src.gate.github_review import post_github_review
from src.models.analysis import Analysis
from src.models.repository import Repository
from src.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter()

HANDLED_EVENTS = {"push", "pull_request"}


@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    payload = await request.body()

    if not verify_github_signature(payload, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event not in HANDLED_EVENTS:
        return {"status": "ignored"}

    data = json.loads(payload)
    background_tasks.add_task(run_analysis_pipeline, x_github_event, data)
    return {"status": "accepted"}


async def handle_gate_callback(
    analysis_id: int,
    decision: str,
    decided_by: str,
) -> None:
    db = SessionLocal()
    try:
        analysis = db.query(Analysis).filter_by(id=analysis_id).first()
        if not analysis:
            logger.warning("handle_gate_callback: analysis %d not found", analysis_id)
            return
        repo = db.query(Repository).filter_by(id=analysis.repo_id).first()
        if not repo:
            return
        body = f"{'✅ 승인' if decision == 'approve' else '❌ 반려'} by @{decided_by}"
        await post_github_review(settings.github_token, repo.full_name,
                                  analysis.pr_number, decision, body)
        _save_gate_decision(db, analysis_id, decision, "manual", decided_by)
    except Exception as exc:
        logger.error("Gate callback failed: %s", exc)
    finally:
        db.close()


@router.post("/api/webhook/telegram")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    callback_query = payload.get("callback_query")
    if not callback_query:
        return {"status": "ok"}
    data = callback_query.get("data", "")
    if not data.startswith("gate:"):
        return {"status": "ok"}
    parts = data.split(":")
    if len(parts) != 3:
        return {"status": "ok"}
    _, decision, analysis_id_str = parts
    if decision not in ("approve", "reject"):
        return {"status": "ok"}
    try:
        analysis_id = int(analysis_id_str)
    except ValueError:
        return {"status": "ok"}
    decided_by = callback_query.get("from", {}).get("username", "unknown")
    background_tasks.add_task(
        handle_gate_callback,
        analysis_id=analysis_id,
        decision=decision,
        decided_by=decided_by,
    )
    return {"status": "ok"}
