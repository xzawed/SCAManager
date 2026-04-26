"""GitHub Webhook provider — POST /webhooks/github.

PR / push / issues 이벤트 수신 + 서명 검증 + 파이프라인 위임.
pull_request.closed + merged=true 시 `Closes #N` 키워드로 이슈 자동 close.
"""
from __future__ import annotations

import json
import logging
import re
import time
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
from src.repositories import merge_retry_repo, repository_repo
from src.services.merge_retry_service import process_pending_retries
from src.shared.log_safety import sanitize_for_log
from src.webhook._helpers import get_webhook_secret
from src.webhook.loop_guard import BotInteractionLimiter, has_skip_marker, is_bot_sender
from src.webhook.validator import verify_github_signature
from src.worker.pipeline import run_analysis_pipeline

logger = logging.getLogger(__name__)

# 프로세스 전역 봇 상호작용 리미터 — 모듈 레벨 싱글톤
# Process-wide bot interaction limiter — module-level singleton
_bot_limiter = BotInteractionLimiter()

# D9: check_suite debounce 캐시 — monorepo 이벤트 폭풍 방지 (30초 TTL)
# D9: check_suite debounce cache — prevents monorepo event storms (30s TTL)
# (repo_full_name, head_sha) → monotonic timestamp of last processing
_check_suite_debounce: dict[tuple[str, str], float] = {}
_CHECK_SUITE_DEBOUNCE_TTL = 30.0  # seconds

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
            # exc 본문에 GitHub API 응답 세부사항이 포함될 수 있으므로 타입명만 기록
            # Log only the exception type — exc body may contain GitHub API response details.
            logger.warning(
                "Auto-close failed (repo=%s, issue=%d): %s",
                repo_name, issue_number, type(exc).__name__,
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


def _loop_guard_check(data: dict) -> dict | None:
    """자기 분석 무한 루프 방지 3-layer 체크 — skip 이유 dict 또는 None 반환.
    Three-layer loop guard: returns a skip-reason dict when the event should be
    suppressed, or None when the pipeline should proceed normally.

    Layer 1: kill-switch (scamanager_self_analysis_disabled)
    Layer 2: bot sender detection
    Layer 3: skip marker in commit/PR message + per-repo rate limit
    """
    # 레이어 1: 킬 스위치 — 전체 self-analysis 비활성화
    # Layer 1: kill-switch — disable all self-analysis pipeline
    if settings.scamanager_self_analysis_disabled:
        return {"status": "skipped", "reason": "self_analysis_disabled"}

    full_name = data.get("repository", {}).get("full_name", "")
    commit_msg = (
        data.get("head_commit", {}).get("message", "")
        or data.get("pull_request", {}).get("title", "")
        or ""
    )

    # 레이어 2: 봇 발신자 감지
    # Layer 2: bot sender detection
    if is_bot_sender(data):
        logger.warning(
            "loop_guard: bot sender skipped repo=%s",
            sanitize_for_log(full_name),
        )
        return {"status": "skipped", "reason": "bot_sender"}

    # 레이어 3-a: 커밋 메시지 skip 마커 감지
    # Layer 3-a: skip marker in commit message
    if has_skip_marker(commit_msg):
        logger.info(
            "loop_guard: skip marker detected repo=%s",
            sanitize_for_log(full_name),
        )
        return {"status": "skipped", "reason": "skip_marker"}

    # 레이어 3-b: 리포별 봇 이벤트 슬라이딩 윈도우 레이트 리밋
    # Layer 3-b: per-repo sliding-window bot event rate limit
    if not _bot_limiter.allow(full_name):
        logger.warning(
            "loop_guard: bot rate limit exceeded repo=%s",
            sanitize_for_log(full_name),
        )
        return {"status": "skipped", "reason": "bot_rate_limit"}

    return None


def _run_pipeline(
    background_tasks: BackgroundTasks,
    x_github_event: str | None,
    data: dict,
) -> dict:
    """분석 파이프라인을 백그라운드 태스크로 등록하고 accepted 응답을 반환한다.
    Schedule the analysis pipeline as a background task and return accepted response.
    """
    background_tasks.add_task(run_analysis_pipeline, x_github_event, data)
    return {"status": "accepted"}


async def _preprocess_pull_request(data: dict) -> dict | None:
    """pull_request 이벤트의 action 전처리 — 조기 반환 dict 또는 None(fall-through) 반환.
    Pre-process pull_request action — returns an early-exit dict or None to fall through.

    None 반환 시 caller 는 loop_guard → pipeline 으로 진행한다.
    When None is returned, caller proceeds to loop_guard → pipeline.
    """
    action = data.get("action")
    if action not in PR_HANDLED_ACTIONS:
        return {"status": "ignored"}
    if action == "closed":
        return await _handle_merged_pr_event(data)
    # force-push 감지: synchronize 시 이전 SHA pending 행 포기 처리
    # Force-push guard: abandon stale pending rows on synchronize
    if action == "synchronize":
        await _handle_pr_synchronize(data)
    # 이하 _loop_guard_check / _run_pipeline 으로 fall-through
    # Fall through to _loop_guard_check / _run_pipeline below
    return None


async def _handle_pr_synchronize(data: dict) -> None:  # NOSONAR python:S7503 — caller awaits for uniform interface
    """pull_request.synchronize 이벤트 시 이전 SHA의 pending 재시도 행을 포기 처리한다.
    On pull_request.synchronize, abandon pending retry rows with the old SHA.

    force-push 감지 — 새 SHA로 교체됐으므로 구 SHA의 재시도는 의미 없음.
    Force-push guard — old-SHA retries are no longer relevant after head changed.
    """
    repo_full_name = data.get("repository", {}).get("full_name", "")
    pr_number = data.get("number") or (data.get("pull_request") or {}).get("number", 0)
    new_sha = ((data.get("pull_request") or {}).get("head") or {}).get("sha", "")

    if not (repo_full_name and pr_number and new_sha):
        return

    try:
        with SessionLocal() as db:
            count = merge_retry_repo.abandon_stale_for_pr(
                db,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                current_sha=new_sha,
            )
            if count:
                logger.info(
                    "synchronize: abandoned %d stale retry rows for pr=%d repo=%s",
                    count, pr_number, repo_full_name,
                )
    except (SQLAlchemyError, KeyError, AttributeError) as exc:
        logger.warning(
            "synchronize: abandon_stale_for_pr failed (repo=%s, pr=%d): %s",
            repo_full_name, pr_number, type(exc).__name__,
        )


async def _handle_check_suite_completed(  # NOSONAR python:S7503 — caller awaits for uniform interface
    data: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """check_suite.completed 이벤트 처리 — 해당 SHA의 pending 재시도 행 즉시 트리거.
    Handle check_suite.completed — immediately trigger retry rows for the completed SHA.

    D9 debounce: 동일 (repo, sha) 30초 내 중복 처리 방지.
    D9 debounce: prevents duplicate processing of the same (repo, sha) within 30s.
    """
    action = data.get("action", "")
    # check_suite.completed 만 처리 — requested/rerequested 무시
    # Only handle check_suite.completed — ignore requested/rerequested
    if action != "completed":
        return {"status": "ignored"}

    check_suite = data.get("check_suite") or {}
    head_sha = check_suite.get("head_sha", "")
    repo_full_name = data.get("repository", {}).get("full_name", "")

    if not head_sha or not repo_full_name:
        return {"status": "ignored"}

    # D9: 30초 debounce — monorepo 50개 workflow 이벤트 폭풍 방지
    # D9: 30s debounce — suppresses storm of 50 check_suite events from monorepo workflows
    key = (repo_full_name, head_sha)
    now = time.monotonic()
    if now - _check_suite_debounce.get(key, 0.0) < _CHECK_SUITE_DEBOUNCE_TTL:
        logger.debug(
            "check_suite: debounced (repo=%s, sha=%.7s)", repo_full_name, head_sha
        )
        return {"status": "debounced"}
    _check_suite_debounce[key] = now

    background_tasks.add_task(_trigger_retry_for_sha, repo_full_name, head_sha)
    return {"status": "accepted"}


async def _trigger_retry_for_sha(repo_full_name: str, commit_sha: str) -> None:
    """check_suite.completed 트리거 — 해당 SHA의 pending 재시도 행 즉시 처리.
    Triggered by check_suite.completed — immediately processes pending retry rows for the SHA.

    별도 DB 세션 내에서 실행 (background task) — 웹훅 요청 세션과 독립.
    Runs in a separate DB session (background task) — independent of the webhook request session.
    """
    try:
        with SessionLocal() as db:
            rows = merge_retry_repo.find_pending_by_sha(
                db,
                repo_full_name=repo_full_name,
                commit_sha=commit_sha,
            )
            if not rows:
                return
            ids = [r.id for r in rows]

        with SessionLocal() as db:
            await process_pending_retries(db, only_ids=ids)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "_trigger_retry_for_sha 실패 (repo=%s, sha=%.7s): %s",
            repo_full_name, commit_sha, type(exc).__name__,
        )


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
        early = await _preprocess_pull_request(data)
        if early is not None:
            return early

    if x_github_event == "issues":
        return await _handle_issues_event(data, background_tasks)

    if x_github_event == "check_suite":
        return await _handle_check_suite_completed(data, background_tasks)

    return _loop_guard_check(data) or _run_pipeline(background_tasks, x_github_event, data)
