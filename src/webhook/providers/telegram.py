"""Telegram gate callback provider — POST /api/webhook/telegram.

반자동 Gate 모드에서 Telegram 인라인 키보드 버튼 클릭 콜백을 수신.
HMAC 으로 서명된 callback token 을 검증하고 GitHub Review 를 실행한다.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Annotated

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.config_manager.manager import get_repo_config
from src.database import SessionLocal
from src.gate.engine import save_gate_decision
from src.gate.github_review import merge_pr, post_github_review
from src.repositories import analysis_repo, repository_repo
from src.shared.merge_metrics import log_merge_attempt

logger = logging.getLogger(__name__)

router = APIRouter()


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
                try:
                    log_merge_attempt(
                        db,
                        analysis_id=analysis_id,
                        repo_name=repo.full_name,
                        pr_number=analysis.pr_number,
                        score=score,
                        threshold=config.merge_threshold,
                        success=ok,
                        reason=reason,
                    )
                except Exception as log_exc:  # pylint: disable=broad-except
                    logger.warning(
                        "merge_attempt 기록 실패 (pr=%d): %s",
                        analysis.pr_number, log_exc,
                    )
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


@router.post("/api/webhook/telegram", responses={401: {"description": "Invalid secret token"}})
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
):
    """Telegram 게이트 콜백 수신 엔드포인트.

    TELEGRAM_WEBHOOK_SECRET 설정 시 X-Telegram-Bot-Api-Secret-Token 헤더를 검증한다.
    """
    if settings.telegram_webhook_secret:
        provided = x_telegram_bot_api_secret_token or ""
        if not hmac.compare_digest(provided, settings.telegram_webhook_secret):
            logger.warning("Telegram webhook: invalid or missing secret token")
            raise HTTPException(status_code=401, detail="Invalid secret token")

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
