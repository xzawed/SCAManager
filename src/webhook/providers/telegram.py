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
from src.database import WorkerSessionLocal as SessionLocal
from src.gate._common import ai_review_failed
from src.gate.github_review import post_github_review
from src.i18n.loader import get_text
from src.notifier._language import resolve_notification_language
from src.notifier.telegram import telegram_post_message
from src.notifier.telegram_commands import handle_message_command, parse_cmd_callback
from src.repositories import (
    analysis_repo,
    gate_decision_repo,
    repository_repo,
    user_repo,
)
from src.shared.secure_compare import secure_str_compare
from src.shared.log_safety import sanitize_for_log

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
    # Phase H PR-5C — 발신측 (telegram_gate._make_callback_token) 과 동일한
    # HMAC msg 형식 사용 — `f"gate:{analysis_id}"`. 이전 구현은 `str(analysis_id)`
    # 만 HMAC 해 발신 토큰과 불일치 → 모든 semi-auto 콜백이 401 거부되던
    # functional bug. 12-에이전트 감사 Critical C10 직접 수정.
    # cmd 도메인 (cmd:N) 과의 격리도 본 변경으로 보장 — cross-replay 차단.
    # Phase H PR-5C: align HMAC msg with sender (`f"gate:{id}"` not `str(id)`) —
    # mismatch had caused all semi-auto callbacks to fail with 401. Also restores
    # cmd-domain isolation (Critical C10 from 2026-04-30 audit).
    expected = hmac.new(
        settings.telegram_bot_token.encode(),
        f"gate:{analysis_id}".encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()[:32]
    if not secure_str_compare(expected, callback_token):
        logger.warning("Telegram gate callback: invalid token for analysis_id=%d", analysis_id)
        return None
    return decision, analysis_id, callback_token


async def handle_gate_callback(  # pylint: disable=too-many-locals
    # too-many-locals: authz 검증(user) 추가로 16/15 — 함수 응집 단위 보호 위해 inline disable
    # (testing.md R0914 결정 트리: 기존 함수 시그니처 확장 시 inline disable + 사유)
    analysis_id: int,
    decision: str,
    decided_by: str,
    telegram_user_id: str | None = None,
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
            # 🔴 authorization (보안): 콜백을 클릭한 Telegram 사용자가 해당 repo 소유자인지 검증.
            # 텍스트 명령 경로(telegram_commands.py: repo.user_id != user.id)와 대칭 — HMAC 토큰은
            # gate:{analysis_id} 만 서명(사용자 신원 무관)하므로, 이 검증이 없으면 버튼을 받은 임의
            # 사용자가 PR 승인/머지를 실행할 수 있다 (broken access control). 미연동/비소유자는 차단.
            # Authorization: verify the clicking Telegram user owns the repo (mirrors the
            # text-command path). The HMAC token signs only gate:{analysis_id} (identity-agnostic),
            # so without this any user who receives the button could approve/merge a PR.
            user = (
                user_repo.find_by_telegram_user_id(db, telegram_user_id)
                if telegram_user_id else None
            )
            if user is None or repo.user_id != user.id:
                logger.warning(  # NOSONAR python:S5145 — sanitized via log_safety
                    "handle_gate_callback: unauthorized tg_user=%s for repo=%s (analysis %d) — skipping",
                    sanitize_for_log(telegram_user_id), sanitize_for_log(repo.full_name), analysis_id,  # C20
                )
                return
            if analysis.pr_number is None:
                # push 이벤트로 생성된 Analysis는 pr_number=None — GitHub Review 불가
                # Analysis created from push event has no pr_number — GitHub Review unavailable
                logger.warning(
                    "handle_gate_callback: analysis %d has no pr_number, skipping gate action",
                    analysis_id,
                )
                return
            # 🔴 리플레이 가드 (#11): 부수효과(GitHub 리뷰·결정 뒤집기·auto-merge) 전에 결정을
            # 원자적으로 claim 한다 — UNIQUE(analysis_id) INSERT 로 first-writer-wins. 이미 결정됐거나
            # 동시 리플레이(더블클릭/Telegram 재전송) 패자는 IntegrityError→False 로 부수효과를 skip.
            # callback_data HMAC 은 gate:{analysis_id} 만 서명(nonce 무관)이라 동일 버튼이 무한 재사용
            # 가능 → claim 이 단일 동기화 지점. upsert 대신 insert-only claim 으로
            # 결정 뒤집기까지 차단(#780 save_new / #787 _ensure_repo 동형 race-safe 패턴).
            # Replay guard (#11): atomically claim the decision before any side effect. A UNIQUE
            # (analysis_id) INSERT makes it first-writer-wins; an existing decision or a concurrent
            # replay (double-click / Telegram retry) loses with IntegrityError→False and skips side
            # effects. The HMAC signs only gate:{analysis_id} (no nonce), so the claim is the single
            # synchronization point — insert-only (no flip), mirroring #780/#787 race-safe pattern.
            if not gate_decision_repo.claim_decision(db, analysis_id, decision, "manual", decided_by):
                logger.info(
                    "handle_gate_callback: analysis %d already decided — skipping replay",
                    analysis_id,
                )
                return
            github_token = (
                repo.owner.plaintext_token
                if repo.owner and repo.owner.plaintext_token
                else settings.github_token
            )
            # GitHub PR Review body 는 리포 협업자 전체에게 영구 노출 — 발신 언어 i18n (사이클 154 P0)
            # The PR Review body is permanently visible to all collaborators — i18n it (Cycle 154 P0)
            config = get_repo_config(db, repo.full_name)
            language = resolve_notification_language(db, config=config)
            body_key = (
                "notifier.gate.manual_approve_body"
                if decision == "approve"
                else "notifier.gate.manual_reject_body"
            )
            body = get_text(body_key, language, decided_by=decided_by)
            await post_github_review(
                github_token, repo.full_name,
                analysis.pr_number, decision, body,
            )
            # 결정은 위 claim 단계에서 이미 원자적으로 기록됨 (별도 저장 불필요)
            # The decision was already recorded atomically by the claim above (no save needed)
            result_dict = analysis.result if isinstance(analysis.result, dict) else {}
            score = result_dict.get("score", analysis.score or 0)
            # 반자동 auto-merge 를 자동 경로(engine._run_auto_merge)에 위임 — retry 큐잉·
            # SHA 원자성 가드·CI 재판별·terminal/deferred 알림까지 자동/반자동 완전 대칭 (Q1 A).
            # _run_auto_merge 가 자체 SessionLocal 을 열고 auto_merge/threshold 가드를 내부 수행한다.
            # 가드는 자동 경로 AutoMergeAction 미러링: (1) 승인 결정만 머지(reject 시 금지),
            # (2) auto_merge 활성, (3) 정적분석 불완전(타임아웃) 시 차단(#779/#783),
            # (4) AI 리뷰 실제 실패(api_error/parse_error) 시 차단(#8 — 인플레 점수 자동 머지 방지).
            # Delegate semi-auto merge to the automatic path for full parity (retry queue, SHA guard,
            # CI re-check, terminal/deferred notifications). _run_auto_merge opens its own session and
            # applies the auto_merge/threshold guard internally. Guards mirror AutoMergeAction:
            # (1) merge only on approve, (2) auto_merge enabled, (3) skip on incomplete static analysis,
            # (4) skip on genuine AI review failure (#8).
            if (
                decision == "approve"
                and config.auto_merge
                and not result_dict.get("static_analysis_incomplete")
                and not ai_review_failed(result_dict)
            ):
                from src.gate import engine  # pylint: disable=import-outside-toplevel
                await engine._run_auto_merge(  # pylint: disable=protected-access
                    config, github_token, repo.full_name, analysis.pr_number, score,
                    analysis_id=analysis_id, result=result_dict,
                )
        except (httpx.HTTPError, KeyError, ValueError, RuntimeError, SQLAlchemyError):
            # Phase H PR-6A: logger.exception 으로 stack trace 보존
            # RuntimeError 포함 — _run_auto_merge(legacy 경로)가 누출할 수 있어 콜백 격리 보강
            # Include RuntimeError — _run_auto_merge (legacy path) may leak it; isolate the callback
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


@router.post(
    "/api/webhook/telegram",
    responses={
        400: {"description": "Invalid request body"},
        401: {"description": "Invalid secret token"},
    },
)
async def telegram_webhook(  # pylint: disable=too-many-locals
    # too-many-locals: 콜백 소유권 전달용 telegram_user_id 추가로 16/15 (inline disable + 사유)
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
):
    """Telegram 게이트 콜백 + 텍스트 명령 수신 엔드포인트.
    Telegram gate callback and text command receiver endpoint.

    TELEGRAM_WEBHOOK_SECRET 설정 시 X-Telegram-Bot-Api-Secret-Token 헤더를 검증한다.
    Validates X-Telegram-Bot-Api-Secret-Token header when TELEGRAM_WEBHOOK_SECRET is set.
    """
    if not settings.telegram_webhook_secret:
        # 시크릿 미설정 — fail-closed: 인증 없이 요청 수락 차단 (S1 보안 강화)
        # Fail-closed when secret is not configured — reject unauthenticated access
        logger.warning("Telegram webhook: TELEGRAM_WEBHOOK_SECRET not configured, rejecting request")
        raise HTTPException(status_code=401, detail="Webhook not configured")
    provided = x_telegram_bot_api_secret_token or ""
    if not secure_str_compare(provided, settings.telegram_webhook_secret):
        logger.warning("Telegram webhook: invalid or missing secret token")
        raise HTTPException(status_code=401, detail="Invalid secret token")

    # 🔴 본문 파싱 robustness (#13): secret 통과 후 비정형/비-dict 본문이 미처리 500 을 내지
    # 않도록 방어 — railway provider 와 대칭(잘못된 client 요청은 400). malformed JSON 은
    # JSONDecodeError, 비-dict(array/scalar) 본문은 이어지는 payload.get 의 AttributeError 유발.
    # Body-parse robustness (#13): after the secret check, guard against malformed/non-dict bodies
    # that would otherwise raise an unhandled 500 — reject as 400 (symmetric with railway provider).
    try:
        payload = await request.json()
    except Exception:  # pylint: disable=broad-except
        logger.warning("Telegram webhook: malformed JSON body")
        raise HTTPException(status_code=400, detail="Invalid JSON body") from None
    if not isinstance(payload, dict):
        logger.warning("Telegram webhook: non-dict JSON body (%s)", type(payload).__name__)
        raise HTTPException(status_code=400, detail="Invalid JSON body")

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
    # 클릭 사용자 telegram_user_id 를 소유권 검증용으로 전달 (str 정규화, 부재 시 None → 차단)
    # Pass the clicking user's telegram_user_id for the ownership check (None → blocked)
    telegram_user_id = str(user_id) if user_id != "unknown" else None
    background_tasks.add_task(
        handle_gate_callback,
        analysis_id=analysis_id,
        decision=decision,
        decided_by=decided_by,
        telegram_user_id=telegram_user_id,
    )
    return {"status": "ok"}
