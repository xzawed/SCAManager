"""GitHub Webhook provider — POST /webhooks/github.

PR / push / issues 이벤트 수신 + 서명 검증 + 파이프라인 위임.
pull_request.closed + merged=true 시 `Closes #N` 키워드로 이슈 자동 close.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.config_manager.manager import get_repo_config
from src.constants import HANDLED_EVENTS, PR_HANDLED_ACTIONS
from src.database import SessionLocal
from src.github_client.issues import close_issue
from src.notifier.n8n import notify_n8n_issue
from src.repositories import repository_repo
from src.webhook._helpers import get_webhook_secret
from src.webhook.validator import verify_github_signature
from src.worker.pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()

# ReDoS 방지: `\s*:?\s*` 의 ambiguous matching 제거 — `[\s:]*` 단일 class 로 통합.
# 동일 입력 매칭 동작 유지 ("closes #1" / "closes: #1" / "closes:#1" 모두 match).
_CLOSING_KEYWORDS = re.compile(r"(?i)\b(?:closes|fixes|resolves)[\s:]*#(\d+)")


def _extract_closing_issue_numbers(body: str | None) -> list[int]:
    """PR body 에서 'Closes|Fixes|Resolves #N' 키워드를 파싱해 이슈 번호 목록 반환."""
    if not body:
        return []
    seen: set[int] = set()
    result: list[int] = []
    for match in _CLOSING_KEYWORDS.finditer(body):
        n = int(match.group(1))
        if n not in seen:
            seen.add(n)
            result.append(n)
    return result


async def _handle_merged_pr_event(data: dict) -> dict:
    """pull_request.closed + merged=true 시 PR body 의 Closes #N 키워드로 Issue 를 close."""
    pr = data.get("pull_request") or {}
    if not pr.get("merged"):
        return {"status": "ignored"}

    body = pr.get("body") or ""
    numbers = _extract_closing_issue_numbers(body)
    if not numbers:
        return {"status": "ignored"}

    repo_name = data.get("repository", {}).get("full_name", "")
    if not repo_name:
        return {"status": "ignored"}

    token = ""
    try:
        with SessionLocal() as db:
            repo = repository_repo.find_by_full_name(db, repo_name)
            if repo and repo.owner:
                token = repo.owner.plaintext_token or ""
    except (SQLAlchemyError, KeyError, AttributeError) as exc:
        logger.warning("merged-pr issue close: repo lookup failed for %s: %s", repo_name, exc)

    token = token or settings.github_token
    if not token:
        logger.info("merged-pr issue close: no token available for %s — skipped", repo_name)
        return {"status": "ignored"}

    for issue_number in numbers:
        try:
            await close_issue(
                token=token,
                repo_full_name=repo_name,
                issue_number=issue_number,
            )
            logger.info("Auto-closed issue #%d on %s (PR merge)", issue_number, repo_name)
        except httpx.HTTPError as exc:
            logger.warning(
                "Auto-close failed (repo=%s, issue=%d): %s", repo_name, issue_number, exc
            )

    return {"status": "accepted"}


async def _handle_issues_event(data: dict, background_tasks: BackgroundTasks) -> dict:
    """GitHub Issues 이벤트를 n8n으로 릴레이한다."""
    repo_name = data.get("repository", {}).get("full_name", "")
    if not repo_name:
        return {"status": "ignored"}

    n8n_url = None
    repo_token = ""
    try:
        with SessionLocal() as db:
            config = get_repo_config(db, repo_name)
            n8n_url = config.n8n_webhook_url
            repo = repository_repo.find_by_full_name(db, repo_name)
            if repo and repo.owner:
                repo_token = repo.owner.plaintext_token or ""
    except (SQLAlchemyError, KeyError, AttributeError) as exc:
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
        repo_token=repo_token,
    )
    return {"status": "accepted"}


@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Annotated[str | None, Header()] = None,
    x_github_event: Annotated[str | None, Header()] = None,
):
    """GitHub Webhook 수신 엔드포인트 — HMAC 서명 검증 후 이벤트를 파이프라인에 위임한다."""
    payload = await request.body()

    full_name = ""
    try:
        data = json.loads(payload)
        full_name = data.get("repository", {}).get("full_name", "")
    except (json.JSONDecodeError, AttributeError):
        data = {}

    secret = get_webhook_secret(full_name) if full_name else settings.github_webhook_secret

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
        if action not in PR_HANDLED_ACTIONS:
            return {"status": "ignored"}
        if action == "closed":
            return await _handle_merged_pr_event(data)

    if x_github_event == "issues":
        return await _handle_issues_event(data, background_tasks)

    background_tasks.add_task(run_analysis_pipeline, x_github_event, data)
    return {"status": "accepted"}
