import json
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Header
from src.config import settings
from src.webhook.validator import verify_github_signature
from src.worker.pipeline import run_analysis_pipeline

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
