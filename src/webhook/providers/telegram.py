"""Telegram gate callback provider — POST /api/webhook/telegram.

반자동 Gate 모드에서 Telegram 인라인 키보드 버튼 클릭 콜백을 수신.
HMAC 으로 서명된 callback token 을 검증하고 GitHub Review 를 실행한다.
Semi-auto gate mode: receives Telegram inline-keyboard button callbacks,
validates HMAC-signed callback token, and executes GitHub Review.
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
from src.notifier.telegram import telegram_post_message
from src.notifier.telegram_commands import handle_message_command, parse_cmd_callback
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
    # 32자 hex (128-bit) — telegram_gate.py 의 발신 토큰과 동일 절단 길이 유지
    # 32 hex chars (128-bit) — matches the truncation length in telegram_gate._gate_callback_token.
    # Telegram callback_data 64-byte 한도로 인해 [:32] 절단이 필수 (NIST SP 800-107 충족).
    # [:32] truncation is required by Telegram's 64-byte callback_data limit (meets NIST SP 800-107).
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
                ok, reason, *_ = await merge_pr(github_token, repo.full_name, analysis.pr_number)
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
        except (httpx.HTTPError, KeyError, ValueError, SQLAlchemyError):
            # Phase H PR-6A: logger.exception 으로 stack trace 보존
            logger.exception("Gate callback failed")


def _handle_message(
    data: dict,
    background_tasks: BackgroundTasks,
    bot_token: str,
) -> dict:
    """Telegram message 이벤트를 처리한다.
    Handle a Telegram message event (text commands).

    텍스트 명령(/start, /connect, /stats, /settings)을 수신해
    handle_message_command로 위임하고 응답을 background에서 전송한다.
    Receives text commands and delegates to handle_message_command,
    sending the reply in background.
    """
    message = data.get("message") or {}
    text = message.get("text") or ""
    # 텍스트 없으면 처리 불필요
    # No text — nothing to process
    if not text:
        return {"status": "ok"}

    sender = message.get("from") or {}
    sender_id = str(sender.get("id", ""))
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))

    # 발신자 또는 채팅 ID 없으면 처리 불필요
    # Missing sender or chat ID — skip
    if not sender_id or not chat_id:
        return {"status": "ok"}

    with SessionLocal() as db:
        # 텍스트 명령 처리 후 응답 텍스트 반환
        # Process text command and obtain reply text
        reply = handle_message_command(db=db, telegram_user_id=sender_id, text=text)

    # 응답 메시지 비동기 전송 (background)
    # Send reply message asynchronously in background
    background_tasks.add_task(
        telegram_post_message,
        bot_token,
        chat_id,
        {"text": reply, "parse_mode": "HTML"},
    )
    return {"status": "ok"}


@router.post("/api/webhook/telegram", responses={401: {"description": "Invalid secret token"}})
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
):
    """Telegram 게이트 콜백 + 텍스트 명령 수신 엔드포인트.
    Telegram gate callback and text command receiver endpoint.

    TELEGRAM_WEBHOOK_SECRET 설정 시 X-Telegram-Bot-Api-Secret-Token 헤더를 검증한다.
    Validates X-Telegram-Bot-Api-Secret-Token header when TELEGRAM_WEBHOOK_SECRET is set.
    """
    if settings.telegram_webhook_secret:
        provided = x_telegram_bot_api_secret_token or ""
        if not hmac.compare_digest(provided, settings.telegram_webhook_secret):
            logger.warning("Telegram webhook: invalid or missing secret token")
            raise HTTPException(status_code=401, detail="Invalid secret token")

    payload = await request.json()

    # message.text 분기: 텍스트 명령 처리
    # message.text branch: handle text commands
    if payload.get("message"):
        return _handle_message(payload, background_tasks, settings.telegram_bot_token)

    callback_query = payload.get("callback_query")
    if not callback_query:
        # message도 callback_query도 없는 알 수 없는 페이로드 — 무시
        # Unknown payload with neither key — ignore gracefully
        return {"status": "ok"}

    callback_data = callback_query.get("data", "")

    # cmd: 접두사 콜백 위임
    # cmd: prefix callback dispatch
    if callback_data.startswith("cmd:"):
        cmd = parse_cmd_callback(callback_data)
        if cmd is not None:
            # 향후 cmd 동작 처리 자리 (현재: 기능 준비 중)
            # Placeholder for future cmd action handling (currently: feature in progress)
            logger.debug("cmd: callback received — verb=%s, payload_id=%s", cmd.verb, cmd.payload_id)
        return {"status": "ok"}

    # gate: 접두사 콜백 처리 (기존 로직 완전 보존)
    # gate: prefix callback handling (existing logic fully preserved)
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
