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

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from src.config import settings
from src.config_manager.manager import get_repo_config
from src.database import WorkerSessionLocal as SessionLocal
from src.gate._common import ai_review_failed
from src.gate.github_review import HeadMovedError, post_github_review
from src.i18n.loader import get_text
from src.notifier._language import resolve_notification_language
from src.shared.http_client import HTTPX_SEND_ERRORS
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
    chat_id: str | None = None,
) -> None:
    """Telegram 인라인 키보드 콜백을 처리해 GitHub Review 결정을 실행한다.

    chat_id: 실패 시 버튼 누른 채팅으로 미게시 알림을 보낼 때 사용 (None 이면 알림 skip).
    chat_id: used to notify the clicker when the GitHub review was NOT posted (skip if None).
    """
    with SessionLocal() as db:
        # 실패 알림 언어 — post 직전 resolve 결과를 except 에서 재사용 (미설정 시 default fallback)
        # Language for failure notice — reuse the value resolved before post (default if unset)
        language: str | None = None
        # 🔴 GitHub 리뷰가 **실제로 게시됐는지** — 실패 알림 문구가 이 값에 달려 있다.
        #    `post_github_review` 는 성공했는데 그 뒤 `_run_auto_merge` 가 예외를 내면
        #    아래 broad except 로 떨어진다. 이 플래그가 없으면 그때도 «게시되지 않았습니다» 를
        #    보내게 되는데 그것은 **거짓**이다 — 리뷰는 GitHub 에 붙어 있다.
        #    실측 적발: `#1412`(fcad25ca) 가 그 상태로 머지됐다.
        # Whether the GitHub review actually landed; the failure notice text depends on it,
        # because a post-success + auto-merge-failure falls into the same broad except.
        review_posted = False
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
            gate_decision_repo.claim_decision(db, analysis_id, decision, "manual", decided_by)
            # 🔴 클레임에 **졌다고 곧바로 리플레이가 아니다** (#1504 R2). 결정은 기록됐는데
            #    게시가 전송 오류로 실패한 행(`pending_post`)이 있고, 그때는 **재시도가 맞다**.
            #    게시 여부를 가르는 것은 아래 in-flight 클레임이다:
            #      얻으면   → 아직 안 붙었고 다른 클릭도 게시 중이 아니다 → 게시한다
            #      못 얻으면 → 이미 붙었거나(`posted`) 다른 클릭이 게시 중이다 → 리플레이
            # 🔴 `state == pending_post` 만 보고 게시하면 두 클릭이 둘 다 POST 해 **중복 리뷰**가
            #    난다 — 배타적 클레임이라야 한다(Grok claim-review `01a05767`).
            # Losing the decision claim is not by itself a replay: a decision whose post failed is
            # retryable. The exclusive begin-post claim below is what separates the two.
            claimed = gate_decision_repo.claim_post_attempt(db, analysis_id)
            if claimed is None:
                logger.info(
                    "handle_gate_callback: analysis %d already posted or posting — skipping replay",
                    analysis_id,
                )
                # 🔴 부수효과는 skip 하되 **무음이면 안 된다** (#1431). 이 분기에 도달하는 가장 흔한
                #    경로는 동시 더블클릭이 아니라 «게시 실패 안내를 받고 다시 누른 사람» 이다.
                #    그때 아무 응답이 없으면 사용자는 대기하고, DB 에는 승인이 남아 있고,
                #    GitHub 에는 리뷰가 없다 — 세 상태가 서로 다른 말을 한다.
                # 🔴 문구는 «미게시» 라고 단정하지 않는다. 리뷰가 이미 붙어 있을 수도 있어서
                #    (첫 클릭이 게시까지 성공한 뒤 auto-merge 에서 터진 경우) 단정하면 거짓이 된다.
                #    이것이 `#1414` 가 고친 것과 같은 클래스의 실수다.
                # Skip side effects but do not stay silent: the usual caller here is a human who was
                # told the review was not posted and pressed again. The wording must not assert
                # "not posted" — the review may in fact be live.
                await _notify_replay_blocked(db, chat_id, analysis_id)
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
            # 🔴 **클레임된 결정**을 게시한다 — 이 클릭의 `decision` 이 아니다 (#1504 R2).
            #    HMAC 은 `gate:{analysis_id}` 만 서명하므로, 재시도가 새 클릭의 결정을
            #    게시하면 `claim_decision` 이 막던 approve→reject **뒤집기**가 되살아난다.
            # Post the CLAIMED decision, never the new click's: the HMAC carries no decision,
            # so honouring it on retry would re-open the flip the claim exists to prevent.
            decision = claimed.decision
            body_key = (
                "notifier.gate.manual_approve_body"
                if decision == "approve"
                else "notifier.gate.manual_reject_body"
            )
            body = get_text(body_key, language, decided_by=claimed.decided_by or decided_by)
            await post_github_review(
                github_token, repo.full_name,
                analysis.pr_number, decision, body,
                # 🔴 분석 SHA 결속 — semi-auto 승인 버튼(무만료 HMAC)을 몇 시간 뒤 눌러도 그 사이
                # head 가 이동했으면 리뷰를 붙이지 않는다(fail-closed, 준비도 감사 #8).
                # 🔴 강제 주체 정정 (owed #1072, 2026-07-26): 이전 주석은 "GitHub 이 422 로 거부"
                # 라고 적었으나 실측에서 **거짓**으로 확인됐다(구 SHA 도 GitHub 은 200 수락).
                # 결속은 post_github_review 가 POST 전에 head 를 조회해 직접 강제한다.
                commit_id=analysis.commit_sha,
            )
            # 🔴 여기를 지나면 리뷰는 GitHub 에 **붙어 있다**. 이 뒤의 어떤 실패도
            #    «게시되지 않았습니다» 로 알리면 거짓이다.
            # Past this point the review is live on GitHub; a "not posted" notice would be a lie.
            review_posted = True
            # 🔴 auto-merge **전에** 못 박는다 — 그 뒤가 터져도 리뷰는 붙어 있으므로
            #    재시도 대상이 아니다. `review_posted = True` 와 같은 경계다 (#1504 R2).
            gate_decision_repo.mark_posted(db, analysis_id)
            # 결정은 위 claim 단계에서 이미 원자적으로 기록됨 (별도 저장 불필요)
            # The decision was already recorded atomically by the claim above (no save needed)
            result_dict = analysis.result if isinstance(analysis.result, dict) else {}
            score = result_dict.get("score", analysis.score or 0)
            # 반자동 auto-merge 를 자동 경로(engine._run_auto_merge)에 위임 — retry 큐잉·
            # SHA 원자성 가드·CI 재판별·terminal/deferred 알림까지 자동/반자동 완전 대칭 (Q1 A).
            # _run_auto_merge 가 자체 SessionLocal 을 열고 auto_merge/threshold 가드를 내부 수행한다.
            # 가드는 자동 경로 AutoMergeAction 미러링: (1) 승인 결정만 머지(reject 시 금지),
            # (2) auto_merge 활성, (3) 정적분석 불완전(타임아웃) 시 차단(#779/#783),
            # (4) AI 리뷰 실제 실패(api_error/parse_error) 시 차단(#8 — 인플레 점수 자동 머지 방지),
            # (5) AI 리뷰 diff 절단 시 차단(C22 — 잘린 일부만 본 인플레 점수 자동 머지 방지).
            # 🔴 (6) SHA 결속(analyzed_sha=analysis.commit_sha) — 본 경로는 자동 경로보다 노출이 크다:
            # 콜백 HMAC 은 gate:{analysis_id} 만 서명하고 만료가 없어(_make_callback_token) 승인 버튼을
            # 몇 시간 뒤 눌러도 유효하다. 결속이 없으면 그 시점의 head(= 분석된 적 없는 커밋)가 이
            # analysis 의 점수로 머지된다 — 레이스조차 필요 없다. engine 이 head 와 비교해 차단한다.
            # 🔴 (6) SHA binding — this path is more exposed than the automatic one: the callback HMAC
            # signs only gate:{analysis_id} and never expires, so a stale approve button clicked hours
            # later would merge whatever the head is now under this analysis's score — no race needed.
            # Passing analyzed_sha lets the engine compare against the live head and refuse.
            # Delegate semi-auto merge to the automatic path for full parity (retry queue, SHA guard,
            # CI re-check, terminal/deferred notifications). _run_auto_merge opens its own session and
            # applies the auto_merge/threshold guard internally. Guards mirror AutoMergeAction:
            # (1) merge only on approve, (2) auto_merge enabled, (3) skip on incomplete static analysis,
            # (4) skip on genuine AI review failure (#8), (5) skip on truncated AI-review diff (C22).
            if (
                decision == "approve"
                and config.auto_merge
                and not result_dict.get("static_analysis_incomplete")
                and not ai_review_failed(result_dict)
                and not result_dict.get("ai_review_truncated")
            ):
                from src.gate import engine  # pylint: disable=import-outside-toplevel
                await engine._run_auto_merge(  # pylint: disable=protected-access
                    config, github_token, repo.full_name, analysis.pr_number, score,
                    analysis_id=analysis_id, result=result_dict,
                    analyzed_sha=analysis.commit_sha,
                )
        except HeadMovedError as exc:
            # 🔴 분석 SHA ≠ 현재 head — 정상 fail-closed. 이 경로는 노출이 가장 크다(무만료 HMAC).
            # 🔴 여기서 잡아야 하는 이유 (실측): HeadMovedError 는 Exception 직계라 (a) 아래 broad
            # except 튜플에도, (b) 상위 래퍼 `_handle_gate_callback_guarded` 의
            # `(*HTTPX_SEND_ERRORS, SQLAlchemyError)` 에도 걸리지 않는다 → BackgroundTask 밖으로 탈출해
            # uvicorn 이 트레이스백을 찍는다. 즉 **정상 fail-closed 가 크래시로 보고**돼 진짜 장애와
            # 구분되지 않는다. 예외 전파로 아래 auto-merge 는 자연 skip 된다.
            # ⚠️ 정확성 — 이 예외 메시지는 SHA 뿐이라 **credential 을 담지 않는다**. 형제 래퍼가
            # 존재하는 이유(토큰이 URL 에 실리는 httpx 오류, `_post_message_guarded` docstring)와
            # 혼동 금지: 여기서의 해악은 유출이 아니라 **오탐 크래시 보고**다.
            # 🔴 Caught here because it is a subclass of neither the broad tuple below nor the outer
            # wrapper's — it would escape the BackgroundTask and be logged as a crash.
            # ⚠️ Its message carries SHAs only, no credential (unlike the httpx case).
            logger.info(
                "Gate callback: head moved since analysis — GitHub Review 미게시 (fail-closed): "
                "analysis=%d (%s)", analysis_id, exc,
            )
            # 갈래 A: claim 은 유지(철회 없음). 버튼 누른 사람에게 리뷰 미게시만 알린다.
            # Branch A: keep the claim (no retraction). Only tell the clicker the review was NOT posted.
            # 🔴 in-flight 리스만 푼다 — 결정은 남기고 **재시도만** 열어 준다 (#1504 R2).
            #    head 가 되돌아올 일은 없으니 다음 클릭도 같은 곳에서 빠르게 실패하지만,
            #    리스만큼 기다리게 하지 않는 것이 맞다. `state` 는 건드리지 않는다.
            gate_decision_repo.release_post_claim(db, analysis_id)
            # 🔴 예외 문자열은 사용자 메시지에 넣지 않는다 — httpx 형제 경로가 URL 에 토큰을 실음.
            # 🔴 Never put exception text in the user message — sibling httpx paths embed the bot token.
            if chat_id is not None:
                text = get_text(
                    "notifier.gate.callback_head_moved",
                    language or resolve_notification_language(db, config=None),
                )
                await _post_message_guarded(
                    settings.telegram_bot_token,
                    chat_id,
                    {"text": text, "parse_mode": "HTML"},
                )
        except (*HTTPX_SEND_ERRORS, KeyError, ValueError, RuntimeError, SQLAlchemyError):
            # Phase H PR-6A: logger.exception 으로 stack trace 보존
            # RuntimeError 포함 — _run_auto_merge(legacy 경로)가 누출할 수 있어 콜백 격리 보강
            # Include RuntimeError — _run_auto_merge (legacy path) may leak it; isolate the callback
            logger.exception("Gate callback failed")
            # 갈래 A: claim 유지 + 실패 알림. 예외 본문(토큰 URL 가능)은 절대 발신하지 않는다.
            # 🔴 **문구는 리뷰가 실제로 붙었는지에 따라 갈린다.** `post_github_review` 가 성공한 뒤
            #    `_run_auto_merge` 가 터지면 여기로 오는데, 그때 «게시되지 않았습니다» 를 보내면
            #    사용자는 (a) 다시 누르거나(무시된다) (b) GitHub 에서 수동 승인해 **중복 리뷰**를
            #    만든다. 게이트가 조용한 것보다 **틀린 말을 하는 것이 나쁘다**.
            # Branch A: keep claim + failure notice. The wording depends on whether the review
            # actually landed — telling the user "not posted" when it is posted causes a duplicate.
            # 🔴 리스를 푼다 — 게시 **전**에 터졌으면 재시도가 열리고, 게시 **후**(auto-merge
            #    실패)라면 `mark_posted` 가 이미 `posted` 로 못 박아 `release_post_claim` 이
            #    아무것도 되돌리지 않는다. 두 경우가 같은 호출로 옳게 갈린다 (#1504 R2).
            # Releasing is correct on both sides: a post-success already moved the row to
            # "posted", which release_post_claim refuses to resurrect.
            gate_decision_repo.release_post_claim(db, analysis_id)
            if chat_id is not None:
                text = get_text(
                    "notifier.gate.callback_posted_then_failed" if review_posted
                    else "notifier.gate.callback_failed",
                    language or resolve_notification_language(db, config=None),
                )
                await _post_message_guarded(
                    settings.telegram_bot_token,
                    chat_id,
                    {"text": text, "parse_mode": "HTML"},
                )


async def _notify_replay_blocked(db, chat_id, analysis_id):
    """리플레이(이미 결정됨)로 부수효과를 skip 했음을 누른 사람에게 알린다 (#1431).

    Tell the clicker their press was a replay, so no side effect ran.

    🔴 **자기 예외를 스스로 삼킨다.** 호출부는 `handle_gate_callback` 의 `try:` **본문 안**이라,
    여기서 새는 예외는 형제 `except (…, KeyError, SQLAlchemyError)` 로 떨어진다. 그 분기는
    `review_posted=False` 이므로 «리뷰가 게시되지 않았습니다» 를 보내는데 — 이건 리플레이다.
    첫 클릭이 게시까지 성공한 뒤 auto-merge 에서 터졌을 수 있어 그 문구는 **거짓이 될 수 있다**.
    `#1414` 가 고친 것과 정확히 같은 클래스이고, 이 함수가 없으면 그 결함이 재생산된다
    (실측 재현: 로케일 키 누락 → `KeyError` → «미게시» 발신).
    Swallows its own errors: the caller sits inside a try whose sibling except would otherwise
    emit a false "not posted" notice for what is actually a replay.

    🔴 문구도 «미게시» 라고 단정하지 않는다 — 같은 이유로 리뷰가 살아 있을 수 있다.
    """
    if chat_id is None:
        return
    try:
        await _post_message_guarded(
            settings.telegram_bot_token,
            chat_id,
            {
                "text": get_text(
                    "notifier.gate.callback_already_decided",
                    resolve_notification_language(db, config=None),
                ),
                "parse_mode": "HTML",
            },
        )
    except (*HTTPX_SEND_ERRORS, KeyError, ValueError, RuntimeError, SQLAlchemyError):
        # 🔴 예외 본문은 로깅하지 않는다 — 형제 발신 경로가 URL 에 봇 토큰을 싣는다.
        # Type name only: sibling send paths embed the bot token in the URL.
        logger.warning(
            "handle_gate_callback: replay notice not delivered for analysis %s", analysis_id,
        )


async def _post_message_guarded(bot_token, chat_id, payload):
    """백그라운드 Telegram 발신 — 예외를 좁게 흡수해 ASGI 밖으로 전파시키지 않는다.
    Guarded background send; never lets the exception escape to the ASGI layer.

    🔴 왜 필요한가 (2026-07-19 2차 회고 P0): 무가드 BackgroundTask 의 예외는 응답 송신 후
    ASGI 밖으로 탈출해 **uvicorn 이 `exc_info` 트레이스백으로 로깅**한다. Telegram API 는
    `https://api.telegram.org/bot<TOKEN>/sendMessage` 처럼 **토큰을 URL 경로**에 담으므로
    `raise_for_status()` 의 401/400/5xx 메시지에 credential 이 그대로 실린다.
    실측: `RuntimeError: Client error '401 Unauthorized' for url '...bot<TOKEN>/sendMessage'`.
    Unguarded background-task exceptions escape to uvicorn, which logs the traceback — and the
    Telegram URL carries the bot token in its path, so the credential lands in the log.

    🔴 리댁션 필터(`src/logging_config.py`)는 심층 방어일 뿐 여기가 근본 차단이다 —
    필터가 트레이스백을 가려주면 **호출처 결함이 보이지 않게** 되므로 양쪽 다 필요하다.
    The redaction filter is defense-in-depth; masking here at the source is the real fix.

    형제 호출처(`gate/actions/approve.py`·`services/cron_service.py`·
    `services/merge_retry_service.py`)와 동일한 `except HTTPX_SEND_ERRORS` 패턴(#1498).
    """
    try:
        await telegram_post_message(bot_token, chat_id, payload)
    except HTTPX_SEND_ERRORS as exc:
        # 🔴 예외 객체(`%s`)가 아니라 **타입명만** 로깅 — str(exc) 에 토큰 URL 이 들어있다.
        # Log the exception *type* only; str(exc) embeds the token-bearing URL.
        logger.warning("telegram background send failed: %s", type(exc).__name__)


async def _handle_gate_callback_guarded(
    *,
    analysis_id: int,
    decision: str,
    decided_by: str,
    telegram_user_id: str | None = None,
    chat_id: str | None = None,
):
    """백그라운드 게이트 콜백 — 위와 동일한 이유로 예외를 흡수한다.
    Guarded gate callback; same rationale as _post_message_guarded.

    `handle_gate_callback` 은 Telegram·GitHub API 를 호출하므로 동일한 credential-in-URL
    트레이스백 노출 경로를 갖는다.

    🔴 `**kwargs` 가 아니라 **명시 파라미터**다 (2026-07-19 회고 P1 — #1122 가 명문화한
    안티패턴이 이 형제 래퍼에만 남아 있었다). kwargs 로 받으면 pylint 가 호출을 검증하지
    못해(`missing-kwoa` 침묵) `handle_gate_callback` 시그니처가 바뀌어도 조용히 어긋난다.
    실제로 `#1122` 작업 중 같은 형태가 자기 테스트의 인자 누락을 숨기고 있었다.
    Explicit params (not **kwargs) so the linter verifies the call and signature drift fails loudly.

    chat_id: 실패 시 미게시 알림 대상 채팅 (부재 시 None → 알림 skip).
    chat_id: chat for the not-posted failure notice (None → skip notify).
    """
    try:
        await handle_gate_callback(
            analysis_id=analysis_id,
            decision=decision,
            decided_by=decided_by,
            telegram_user_id=telegram_user_id,
            chat_id=chat_id,
        )
    except (*HTTPX_SEND_ERRORS, SQLAlchemyError) as exc:
        logger.warning("telegram gate callback failed: %s", type(exc).__name__)


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

    # 응답 메시지 비동기 전송 (background) — 🔴 반드시 가드된 래퍼로 (아래 docstring 참조).
    # Send reply asynchronously in background — must go through the guarded wrapper.
    background_tasks.add_task(
        _post_message_guarded,
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
    # 실패 알림용 chat_id — message.chat.id 방어적 추출 (_handle_message :304-309 미러)
    # chat_id for failure notice — defensive extract of message.chat.id (mirrors _handle_message)
    _msg = (callback_query or {}).get("message") or {}
    _chat = (_msg or {}).get("chat") or {}
    _raw_chat_id = _chat.get("id")
    chat_id = str(_raw_chat_id) if _raw_chat_id is not None else None
    background_tasks.add_task(
        _handle_gate_callback_guarded,
        analysis_id=analysis_id,
        decision=decision,
        decided_by=decided_by,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
    )
    return {"status": "ok"}
