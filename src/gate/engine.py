import logging
from sqlalchemy.orm import Session
from src.config_manager.manager import get_repo_config
from src.gate.github_review import post_github_review, merge_pr
from src.gate.telegram_gate import send_gate_request
from src.models.gate_decision import GateDecision
from src.scorer.calculator import ScoreResult

logger = logging.getLogger(__name__)


async def run_gate_check(
    db: Session,
    github_token: str,
    telegram_bot_token: str,
    repo_full_name: str,
    pr_number: int,
    analysis_id: int,
    score_result: ScoreResult,
) -> None:
    config = get_repo_config(db, repo_full_name)
    if config.gate_mode == "disabled":
        return
    score = score_result.total
    if config.gate_mode == "auto":
        if score >= config.auto_approve_threshold:
            decision = "approve"
            body = f"✅ 자동 승인: 점수 {score}점 (기준: {config.auto_approve_threshold}점 이상)"
        elif score < config.auto_reject_threshold:
            decision = "reject"
            body = f"❌ 자동 반려: 점수 {score}점 (기준: {config.auto_reject_threshold}점 미만)"
        else:
            _save_gate_decision(db, analysis_id, "skip", "auto")
            return
        try:
            await post_github_review(github_token, repo_full_name, pr_number, decision, body)
            _save_gate_decision(db, analysis_id, decision, "auto")
            if decision == "approve" and config.auto_merge:
                merged = await merge_pr(github_token, repo_full_name, pr_number)
                if merged:
                    logger.info("PR #%d auto-merged: %s", pr_number, repo_full_name)
        except Exception as exc:
            logger.error("GitHub Review 실패: %s", exc)
    elif config.gate_mode == "semi-auto":
        if not config.notify_chat_id:
            logger.warning("semi-auto 모드이나 notify_chat_id 미설정: %s", repo_full_name)
            return
        try:
            await send_gate_request(
                bot_token=telegram_bot_token,
                chat_id=config.notify_chat_id,
                analysis_id=analysis_id,
                repo_full_name=repo_full_name,
                pr_number=pr_number,
                score_result=score_result,
            )
        except Exception as exc:
            logger.error("Telegram Gate 요청 실패: %s", exc)


def _save_gate_decision(
    db: Session,
    analysis_id: int,
    decision: str,
    mode: str,
    decided_by: str | None = None,
) -> GateDecision:
    record = GateDecision(analysis_id=analysis_id, decision=decision,
                          mode=mode, decided_by=decided_by)
    db.add(record)
    db.commit()
    return record
