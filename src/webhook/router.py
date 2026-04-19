"""Webhook endpoints — POST /webhooks/github and POST /api/webhook/telegram."""
import hashlib
import hmac
import json
import logging
import re
import time
import httpx
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Header
from sqlalchemy.exc import SQLAlchemyError
from src.config import settings
from src.webhook.validator import verify_github_signature
from src.worker.pipeline import run_analysis_pipeline
from src.gate.engine import save_gate_decision
from src.gate.github_review import post_github_review, merge_pr
from src.config_manager.manager import get_repo_config
from src.database import SessionLocal
from src.repositories import repository_repo, analysis_repo
from src.constants import HANDLED_EVENTS, PR_HANDLED_ACTIONS, WEBHOOK_SECRET_CACHE_TTL
from src.notifier.n8n import notify_n8n_issue
from src.github_client.issues import close_issue

logger = logging.getLogger(__name__)

router = APIRouter()

HANDLED_PR_ACTIONS = PR_HANDLED_ACTIONS  # 하위 호환 별칭

# {full_name: (secret, expiry_monotonic)}
_webhook_secret_cache: dict[str, tuple[str, float]] = {}


def _get_webhook_secret(full_name: str) -> str:
    """per-repo webhook secret을 DB에서 조회한다 (TTL 캐시 적용)."""
    now = time.monotonic()
    cached = _webhook_secret_cache.get(full_name)
    if cached and now < cached[1]:
        return cached[0]
    secret = settings.github_webhook_secret
    try:
        with SessionLocal() as db:
            repo = repository_repo.find_by_full_name(db, full_name)
            if repo and repo.webhook_secret:
                secret = repo.webhook_secret
    except (SQLAlchemyError, KeyError, AttributeError) as exc:
        logger.warning("Per-repo webhook secret lookup failed, using global secret: %s", exc)
    _webhook_secret_cache[full_name] = (secret, now + WEBHOOK_SECRET_CACHE_TTL)
    return secret

_CLOSING_KEYWORDS = re.compile(r"(?i)\b(?:closes|fixes|resolves)\s*:?\s*#(\d+)")


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


@router.post("/webhooks/github", status_code=202)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    """GitHub Webhook 수신 엔드포인트 — HMAC 서명 검증 후 이벤트를 파이프라인에 위임한다."""
    payload = await request.body()

    # payload에서 리포 이름 파싱 (per-repo 시크릿 조회용)
    full_name = ""
    try:
        data = json.loads(payload)
        full_name = data.get("repository", {}).get("full_name", "")
    except (json.JSONDecodeError, AttributeError):
        data = {}

    # 리포별 시크릿 조회 → 없으면 전역 시크릿 fallback (TTL 캐시)
    secret = _get_webhook_secret(full_name) if full_name else settings.github_webhook_secret

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
        if action == "closed":
            return await _handle_merged_pr_event(data)

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


def _parse_gate_callback(data: str) -> "tuple[str, int, str] | None":
    """Telegram 콜백 data 문자열을 파싱하고 HMAC 토큰을 검증한다.

    Returns:
        (decision, analysis_id, callback_token) 또는 검증 실패 시 None.
    """
    if not data.startswith("gate:"):
        return None
    parts = data.split(":")
    if len(parts) != 4:
        return None
    _, decision, analysis_id_str, callback_token = parts
    if decision not in ("approve", "reject"):
        return None
    try:
        analysis_id = int(analysis_id_str)
    except ValueError:
        return None
    expected = hmac.new(
        settings.telegram_bot_token.encode(),
        str(analysis_id).encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()[:32]
    if not hmac.compare_digest(expected, callback_token):
        logger.warning("Telegram gate callback: invalid token for analysis_id=%d", analysis_id)
        return None
    return decision, analysis_id, callback_token


async def handle_gate_callback(
    analysis_id: int,
    decision: str,
    decided_by: str,
) -> None:
    """Telegram 인라인 키보드 콜백을 처리해 GitHub Review 결정을 실행한다."""
    with SessionLocal() as db:
        try:
            analysis = analysis_repo.find_by_id(db, analysis_id)
            if not analysis:
                logger.warning("handle_gate_callback: analysis %d not found", analysis_id)
                return
            repo = repository_repo.find_by_id(db, analysis.repo_id)
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
            save_gate_decision(db, analysis_id, decision, "manual", decided_by)
            config = get_repo_config(db, repo.full_name)
            result_dict = analysis.result if isinstance(analysis.result, dict) else {}
            score = result_dict.get("score", analysis.score or 0)
            if config.auto_merge and score >= config.merge_threshold:
                ok, reason = await merge_pr(github_token, repo.full_name, analysis.pr_number)
                if ok:
                    logger.info("PR #%d manual-approved+auto-merged: %s",
                                analysis.pr_number, repo.full_name)
                else:
                    logger.warning(
                        "PR #%d manual-approved but auto-merge 실패: %s",
                        analysis.pr_number, reason,
                    )
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
    callback_data = callback_query.get("data", "")
    parsed = _parse_gate_callback(callback_data)
    if parsed is None:
        return {"status": "ok"}
    decision, analysis_id, _ = parsed
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
