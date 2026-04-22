"""Gate Engine — 3개 독립 옵션: Review Comment / Approve / Auto Merge."""
import logging
from html import escape

import httpx
from sqlalchemy.orm import Session
from src.config import settings
from src.config_manager.manager import get_repo_config, RepoConfigData
from src.gate._common import score_from_result as _score_from_result
from src.gate.github_review import post_github_review, merge_pr
from src.gate.telegram_gate import send_gate_request
from src.notifier.github_comment import post_pr_comment_from_result as post_pr_comment
from src.notifier.telegram import telegram_post_message
from src.models.gate_decision import GateDecision
from src.repositories import gate_decision_repo

logger = logging.getLogger(__name__)


async def run_gate_check(  # pylint: disable=too-many-positional-arguments,too-many-branches
    repo_name: str,
    pr_number: int | None,
    analysis_id: int,
    result: dict,
    github_token: str,
    db: Session,
    config: RepoConfigData | None = None,
) -> None:
    """PR 이벤트 시 3개 독립 옵션을 각각 실행한다.

    1. Review Comment — pr_review_comment=True 이면 PR에 상세 AI 리뷰 댓글 발송
    2. Approve       — approve_mode에 따라 GitHub APPROVE/REQUEST_CHANGES 또는 Telegram 요청
    3. Auto Merge    — auto_merge=True이고 score >= merge_threshold이면 squash merge

    세 옵션은 완전 독립 — 어떤 조합이든 가능하다.
    pr_number=None(push 이벤트)이면 모든 PR 관련 액션을 건너뛴다.
    config: 이미 로드된 RepoConfigData — None이면 DB에서 직접 조회한다.

    Note: `src/gate/registry.py` + `src/gate/actions/` 에 Protocol 기반
    action 등록 인프라가 갖춰져 있으나, 기존 테스트 호환성 이유로 현재
    엔진은 직접 구현을 유지. 향후 4+ 번째 action 추가 시 REGISTRY 순회로
    전환 고려 (테스트 mock 경로 일괄 업데이트 필요).
    """
    if pr_number is None:
        return

    if config is None:
        config = get_repo_config(db, repo_name)
    score = result.get("score", 0)

    # 1. Review Comment (독립)
    if config.pr_review_comment:
        try:
            await post_pr_comment(
                github_token=github_token,
                repo_name=repo_name,
                pr_number=pr_number,
                result=result,
            )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("PR Review Comment 실패: %s", exc)

    # 2. Approve (독립)
    if config.approve_mode == "auto":
        if score >= config.approve_threshold:
            decision = "approve"
            body = f"✅ 자동 승인: 점수 {score}점 (기준: {config.approve_threshold}점 이상)"
        elif score < config.reject_threshold:
            decision = "reject"
            body = f"❌ 자동 반려: 점수 {score}점 (기준: {config.reject_threshold}점 미만)"
        else:
            save_gate_decision(db, analysis_id, "skip", "auto")
            decision = None
            body = None

        if decision in ("approve", "reject"):
            try:
                await post_github_review(github_token, repo_name, pr_number, decision, body)
                save_gate_decision(db, analysis_id, decision, "auto")
            except (httpx.HTTPError, KeyError) as exc:
                logger.error("GitHub Review 실패: %s", exc)

    elif config.approve_mode == "semi-auto":
        if not config.notify_chat_id:
            logger.warning("semi-auto 모드이나 notify_chat_id 미설정: %s", repo_name)
        else:
            try:
                score_result = _score_from_result(result)
                await send_gate_request(
                    bot_token=settings.telegram_bot_token,
                    chat_id=config.notify_chat_id,
                    analysis_id=analysis_id,
                    repo_full_name=repo_name,
                    pr_number=pr_number,
                    score_result=score_result,
                )
            except (httpx.HTTPError, KeyError) as exc:
                logger.error("Telegram Gate 요청 실패: %s", exc)

    # 3. Auto Merge (독립 — approve_mode 무관)
    if config.auto_merge and score >= config.merge_threshold:
        try:
            ok, reason = await merge_pr(github_token, repo_name, pr_number)
            if ok:
                logger.info("PR #%d auto-merged: %s", pr_number, repo_name)
            else:
                logger.warning(
                    "PR #%d auto-merge 실패 (repo=%s): %s", pr_number, repo_name, reason
                )
                await _notify_merge_failure(
                    repo_name=repo_name,
                    pr_number=pr_number,
                    score=score,
                    threshold=config.merge_threshold,
                    reason=reason or "unknown",
                    chat_id=config.notify_chat_id or settings.telegram_chat_id,
                )
        except (httpx.HTTPError, KeyError) as exc:
            logger.error("Auto Merge 실패: %s", exc)


async def _notify_merge_failure(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    chat_id: str | None,
) -> None:
    """auto_merge 실패를 Telegram 으로 알린다. chat_id 없으면 스킵."""
    if not chat_id or not settings.telegram_bot_token:
        return
    text = (
        "⚠️ <b>Auto Merge 실패</b>\n"
        f"📁 <code>{escape(repo_name)}</code> — PR #{pr_number}\n"
        f"점수: {score}점 (기준 {threshold}점 이상)\n"
        f"사유: <code>{escape(reason)}</code>"
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token,
            chat_id,
            {"text": text, "parse_mode": "HTML"},
        )
    except httpx.HTTPError as exc:
        logger.warning("Telegram merge-failure 알림 실패: %s", exc)


def save_gate_decision(
    db: Session,
    analysis_id: int,
    decision: str,
    mode: str,
    decided_by: str | None = None,
) -> GateDecision:
    """GateDecision 레코드를 저장하고 반환한다 (재시도 시 upsert).

    Thin wrapper — 실제 구현은 `src/repositories/gate_decision_repo.py::upsert`.
    """
    return gate_decision_repo.upsert(db, analysis_id, decision, mode, decided_by)
