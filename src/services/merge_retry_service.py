"""merge_retry_service — pending 재시도 큐 처리 워커 (Phase 12 T9).
merge_retry_service — worker that processes the pending merge retry queue (Phase 12 T9).

claim_batch → 각 행별 GitHub token 조회 → 설정 재확인 → PR 상태 사전 검사
→ merge_pr 호출 → 결과에 따라 succeeded / terminal / released 분기.
claim_batch → per-row GitHub token resolution → config re-check → PR pre-flight
→ call merge_pr → branch to succeeded / terminal / released based on result.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from html import escape

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import settings
from src.config_manager.manager import RepoConfigData, get_repo_config
from src.gate.github_review import merge_pr
from src.gate.merge_failure_advisor import get_advice
from src.gate.retry_policy import (
    compute_next_retry_at,
    is_expired,
    parse_reason_tag,
    should_retry,
)
from src.github_client.checks import get_ci_status, get_required_check_contexts
from src.github_client.helpers import github_api_headers
from src.models.merge_retry import MergeRetryQueue
from src.notifier.merge_failure_issue import create_merge_failure_issue
from src.notifier.telegram import telegram_post_message
from src.repositories import merge_retry_repo, repository_repo, user_repo
from src.shared.http_client import get_http_client
from src.shared.merge_metrics import log_merge_attempt

logger = logging.getLogger(__name__)


async def process_pending_retries(  # pylint: disable=too-many-locals,too-many-statements
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 50,
    only_ids: list[int] | None = None,
) -> dict[str, int]:
    """pending 재시도 큐를 처리한다.
    Process the pending merge retry queue.

    Returns counts dict: {"claimed", "succeeded", "terminal", "abandoned", "released", "skipped"}
    """
    # 현재 시각 설정 — 테스트에서 주입 가능 (freezegun 불필요)
    # Set current time — injectable from tests (no freezegun needed)
    now = now or datetime.now(timezone.utc)

    # 처리 가능한 행을 원자적으로 클레임 (attempts_count += 1 포함)
    # Atomically claim processable rows (includes attempts_count += 1)
    claimed = merge_retry_repo.claim_batch(
        db,
        now=now.replace(tzinfo=None),
        limit=limit,
        stale_after_seconds=300,
        only_ids=only_ids,
    )

    counts: dict[str, int] = {
        "claimed": len(claimed),
        "succeeded": 0,
        "terminal": 0,
        "abandoned": 0,
        "released": 0,
        "skipped": 0,
    }

    for row in claimed:
        try:
            # ── a. GitHub 토큰 조회 ────────────────────────────────────────
            # ── a. Resolve GitHub token ───────────────────────────────────
            token = _resolve_github_token(db, row.repo_full_name)
            if token is None:
                # 토큰 없음 — 30초 후 재시도 대기로 복귀
                # No token — release back to retry queue after 30s
                _now_naive = now.replace(tzinfo=None) + timedelta(seconds=30)
                merge_retry_repo.release_claim(
                    db,
                    row.id,
                    next_retry_at=_now_naive,
                    last_failure_reason="no_token",
                )
                counts["released"] += 1
                continue

            # ── b-0. 최대 시도 횟수 초과 검사 ────────────────────────────────────────
            # ── b-0. Max attempts exhaustion check ─────────────────────────────────
            if row.attempts_count >= row.max_attempts:
                merge_retry_repo.mark_abandoned(
                    db, row.id, reason="max_attempts_exceeded"
                )
                counts["abandoned"] += 1
                continue

            # ── b. 설정 재확인 (D5) ────────────────────────────────────────
            # ── b. Re-read live config (D5) ───────────────────────────────
            cfg = get_repo_config(db, row.repo_full_name)
            if not (cfg.auto_merge and row.score >= cfg.merge_threshold):
                # 설정이 변경되어 자동 머지 조건 미충족 → 포기
                # Config changed so auto-merge condition no longer met → abandon
                merge_retry_repo.mark_abandoned(db, row.id, reason="config_changed")
                await _notify_config_changed(row, cfg)
                counts["abandoned"] += 1
                continue

            # ── c. PR 사전 검사 (D7) ──────────────────────────────────────
            # ── c. Pre-merge guard (D7) ───────────────────────────────────
            pr_data = await _get_pr_data(token, row.repo_full_name, row.pr_number)

            if pr_data is None:
                # PR 데이터 조회 실패 — 30초 후 재시도
                # PR data fetch failed — retry after 30s
                _now_naive = now.replace(tzinfo=None) + timedelta(seconds=30)
                merge_retry_repo.release_claim(
                    db,
                    row.id,
                    next_retry_at=_now_naive,
                    last_failure_reason="pr_fetch_failed",
                )
                counts["released"] += 1
                continue

            # 이미 머지된 PR — 성공으로 처리
            # PR already merged — treat as success
            if pr_data.get("merged") is True:
                merge_retry_repo.mark_succeeded(db, row.id, reason="already_merged")
                counts["succeeded"] += 1
                continue

            # SHA drift 검사 — force-push 감지
            # SHA drift check — detects force-push
            head_sha = pr_data.get("head", {}).get("sha", "")
            if head_sha and head_sha != row.commit_sha:
                merge_retry_repo.mark_abandoned(db, row.id, reason="sha_drift")
                counts["abandoned"] += 1
                continue

            # ── d. merge_pr 호출 ──────────────────────────────────────────
            # ── d. Call merge_pr ──────────────────────────────────────────
            ok, reason, _ = await merge_pr(
                token,
                row.repo_full_name,
                row.pr_number,
                expected_sha=row.commit_sha,
            )

            # ── e. 성공 처리 ──────────────────────────────────────────────
            # ── e. Handle success ─────────────────────────────────────────
            if ok:
                log_merge_attempt(
                    db,
                    analysis_id=row.analysis_id,
                    repo_name=row.repo_full_name,
                    pr_number=row.pr_number,
                    score=row.score,
                    threshold=row.threshold_at_enqueue,
                    success=True,
                    reason=None,
                )
                merge_retry_repo.mark_succeeded(db, row.id)
                await _notify_merge_succeeded(row, cfg)
                counts["succeeded"] += 1
                continue

            # ── f. 실패 분류 ──────────────────────────────────────────────
            # ── f. Classify failure ───────────────────────────────────────
            reason_tag = parse_reason_tag(reason)
            # F1: pr_data 에 이미 base.ref 가 있으므로 추가 호출 없이 활용
            # F1: pr_data already contains base.ref — reuse without extra API call
            base_ref = pr_data.get("base", {}).get("ref", "main")
            ci_status = await _get_ci_status_safe(
                token, row.repo_full_name, row.commit_sha, base_ref=base_ref,
            )

            expired = is_expired(row, now=now, max_age_hours=settings.merge_retry_max_age_hours)

            if (not should_retry(reason_tag, ci_status)) or expired:
                # 재시도 불가 또는 만료 → terminal 처리
                # Non-retryable or expired → terminal
                log_merge_attempt(
                    db,
                    analysis_id=row.analysis_id,
                    repo_name=row.repo_full_name,
                    pr_number=row.pr_number,
                    score=row.score,
                    threshold=row.threshold_at_enqueue,
                    success=False,
                    reason=reason,
                )
                merge_retry_repo.mark_terminal(db, row.id, reason=reason_tag)
                await _notify_merge_terminal(row, cfg, reason, reason_tag)
                if cfg.auto_merge_issue_on_failure:
                    await _create_failure_issue_safe(token, row, cfg, reason, reason_tag)
                counts["terminal"] += 1
                continue

            # ── g. 일시적 실패 — 백오프 후 재시도 대기로 복귀 ────────────
            # ── g. Transient failure — bump and release with backoff ──────
            next_retry_at = compute_next_retry_at(
                row.attempts_count,
                now=now,
                initial_backoff=settings.merge_retry_initial_backoff_seconds,
                max_backoff=settings.merge_retry_max_backoff_seconds,
            )
            merge_retry_repo.release_claim(
                db,
                row.id,
                next_retry_at=next_retry_at.replace(tzinfo=None),  # naive UTC for DB
                last_failure_reason=reason_tag,
                last_detail_message=reason,
            )
            counts["released"] += 1

        except (httpx.HTTPError, SQLAlchemyError) as exc:
            # 인프라 에러 — 클레임 해제, 짧은 백오프, attempts_count 미증가
            # Infra error — release claim, short backoff, do NOT bump attempts_count
            _now_naive = now.replace(tzinfo=None) + timedelta(seconds=30)
            merge_retry_repo.release_claim(
                db,
                row.id,
                next_retry_at=_now_naive,
                last_failure_reason="infra_error",
                last_detail_message=str(exc)[:200],
            )
            logger.warning(
                "retry worker infra error row_id=%d: %s", row.id, type(exc).__name__
            )
            counts["released"] += 1

    return counts


# ---------------------------------------------------------------------------
# Private helpers
# 비공개 헬퍼 함수
# ---------------------------------------------------------------------------


def _resolve_github_token(db: Session, repo_full_name: str) -> str | None:
    """리포 소유자의 GitHub 토큰을 조회한다 — 없으면 settings.github_token fallback.
    Look up the repo owner's GitHub token — falls back to settings.github_token.
    """
    repo = repository_repo.find_by_full_name(db, repo_full_name)
    if repo is not None and repo.user_id is not None:
        user = user_repo.find_by_id(db, repo.user_id)
        if user is not None:
            token = user.plaintext_token
            if token:
                return token
    # 레거시 글로벌 토큰 fallback
    # Legacy global token fallback
    fallback = settings.github_token
    return fallback if fallback else None


async def _get_pr_data(
    token: str, repo_full_name: str, pr_number: int
) -> dict | None:
    """PR 전체 데이터를 조회한다. 실패 시 None 반환.
    Fetch full PR data. Returns None on failure.
    """
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    try:
        client = get_http_client()
        r = await client.get(url, headers=github_api_headers(token))
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError:
        return None


async def _get_ci_status_safe(
    token: str, repo_full_name: str, commit_sha: str, *, base_ref: str = "main"
) -> str:
    """CI 상태를 안전하게 조회한다 — 오류 시 'unknown' 반환.
    Safely fetch CI status — returns 'unknown' on error.

    F1: base_ref 파라미터로 PR 의 실제 base 브랜치 BPR 조회.

    🔴 **PARITY GUARD**: 본 함수는 `src/gate/engine.py::_get_ci_status_safe` 와
    의도적 동일 구현 (단일/워커 경로 일관성). 한쪽만 수정하면 두 경로의 CI
    상태 판정이 발산해 운영 사고. 변경 시 양쪽 동시 수정 필수 +
    `tests/unit/test_ci_status_safe_parity.py` 회귀 가드 통과 확인.

    **PR-5A-2 마이그레이션 가이드**: engine.py 측 동일 함수 docstring 의 §PR-5A-2
    마이그레이션 가이드 참조 — 양쪽 동시 적용 필수.

    INTENTIONAL DUPLICATE — keep both copies in sync; parity test enforces.
    """
    try:
        required = await get_required_check_contexts(token, repo_full_name, base_ref)
    except httpx.HTTPError:
        required = None

    # 방어층: BPR Required 미설정으로 빈 set 이 반환되면 None 으로 통일
    # engine.py::_get_ci_status_safe 와 동일 패턴 — 단일/워커 경로 일관성 확보
    # Defense layer: unify empty set to None for consistency with engine path
    if not required:
        required = None

    try:
        return await get_ci_status(
            token,
            repo_full_name,
            commit_sha,
            required_contexts=required,
        )
    except httpx.HTTPError:
        return "unknown"


async def _notify_config_changed(row: MergeRetryQueue, cfg: RepoConfigData) -> None:
    """설정 변경으로 재시도가 중단됐음을 알린다.
    Notify user that retry was stopped due to config change.
    """
    chat_id = cfg.notify_chat_id or row.notify_chat_id or settings.telegram_chat_id
    if not chat_id or not settings.telegram_bot_token:
        return
    msg = (
        "🚫 <b>자동 머지 재시도 중단</b>\n"
        f"📁 <code>{escape(row.repo_full_name)}</code> — PR #{row.pr_number}\n"
        "<i>설정이 변경되어 재시도가 중단되었습니다 (auto_merge 비활성 또는 점수 기준 변경).</i>\n"
        "<i>Retry stopped: auto_merge disabled or threshold changed.</i>"
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token, chat_id, {"text": msg, "parse_mode": "HTML"}
        )
    except httpx.HTTPError as exc:
        logger.warning("_notify_config_changed 전송 실패: %s", type(exc).__name__)


async def _notify_merge_succeeded(row: MergeRetryQueue, cfg: RepoConfigData) -> None:
    """재시도 후 머지 성공을 알린다 (시도 횟수 포함).
    Notify user of successful merge after retries (includes attempt count).
    """
    chat_id = cfg.notify_chat_id or row.notify_chat_id or settings.telegram_chat_id
    if not chat_id or not settings.telegram_bot_token:
        return
    pr_url = f"https://github.com/{row.repo_full_name}/pull/{row.pr_number}"
    msg = (
        "✅ <b>자동 머지 성공 (재시도)</b>\n"
        f"📁 <code>{escape(row.repo_full_name)}</code> — PR #{row.pr_number}\n"
        f"점수: {row.score}점 | 시도 횟수: {row.attempts_count}회\n"
        f'🔗 <a href="{escape(pr_url)}">GitHub에서 보기</a>'
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token, chat_id, {"text": msg, "parse_mode": "HTML"}
        )
    except httpx.HTTPError as exc:
        logger.warning("_notify_merge_succeeded 전송 실패: %s", type(exc).__name__)


async def _notify_merge_terminal(
    row: MergeRetryQueue,
    cfg: RepoConfigData,
    reason: str | None,
    reason_tag: str,
) -> None:
    """최종 머지 실패를 알린다.
    Notify user of terminal merge failure.
    """
    chat_id = cfg.notify_chat_id or row.notify_chat_id or settings.telegram_chat_id
    if not chat_id or not settings.telegram_bot_token:
        return
    advice = get_advice(reason_tag)
    pr_url = f"https://github.com/{row.repo_full_name}/pull/{row.pr_number}"
    msg = (
        "⚠️ <b>자동 머지 최종 실패</b>\n"
        f"📁 <code>{escape(row.repo_full_name)}</code> — PR #{row.pr_number}\n"
        f"점수: {row.score}점 | 시도 횟수: {row.attempts_count}회\n"
        f"사유: <code>{escape(reason or reason_tag)}</code>\n"
        f"💡 {escape(advice)}\n"
        f'🔗 <a href="{escape(pr_url)}">GitHub에서 보기</a>'
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token, chat_id, {"text": msg, "parse_mode": "HTML"}
        )
    except httpx.HTTPError as exc:
        logger.warning("_notify_merge_terminal 전송 실패: %s", type(exc).__name__)


async def _create_failure_issue_safe(
    token: str,
    row: MergeRetryQueue,
    cfg: RepoConfigData,  # pylint: disable=unused-argument
    reason: str | None,
    reason_tag: str,
) -> None:
    """create_merge_failure_issue 를 안전하게 호출한다 (예외 격리).
    Safely call create_merge_failure_issue (exception-isolated).
    """
    advice = get_advice(reason_tag)
    try:
        await create_merge_failure_issue(
            github_token=token,
            repo_name=row.repo_full_name,
            pr_number=row.pr_number,
            score=row.score,
            threshold=row.threshold_at_enqueue,
            reason=reason or reason_tag,
            advice=advice,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "create_merge_failure_issue 실패 (pr=%d): %s", row.pr_number, exc
        )
