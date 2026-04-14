"""Analysis pipeline — orchestrates static analysis, AI review, scoring, and notifications."""
import asyncio
import logging

from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.config import settings
from src.github_client.diff import get_pr_files, get_push_files, ChangedFile
from src.analyzer.static import analyze_file, StaticAnalysisResult
from src.analyzer.ai_review import review_code
from src.scorer.calculator import calculate_score
from src.notifier.telegram import send_analysis_result
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.gate.engine import run_gate_check
from src.notifier.n8n import notify_n8n
from src.notifier.discord import send_discord_notification
from src.notifier.slack import send_slack_notification
from src.notifier.webhook import send_webhook_notification
from src.notifier.email import send_email_notification
from src.config_manager.manager import get_repo_config
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def _build_result_dict(
    ai_review,
    score_result,
    analysis_results: list,
    source: str,
) -> dict:
    """Build the standardised analysis result dict stored in Analysis.result."""
    return {
        "source": source,
        "score": score_result.total,
        "grade": score_result.grade,
        "breakdown": score_result.breakdown,
        "ai_review_status": ai_review.status,
        "ai_summary": ai_review.summary,
        "ai_suggestions": ai_review.suggestions,
        "commit_message_feedback": ai_review.commit_message_feedback,
        "code_quality_feedback": ai_review.code_quality_feedback,
        "security_feedback": ai_review.security_feedback,
        "direction_feedback": ai_review.direction_feedback,
        "test_feedback": ai_review.test_feedback,
        "file_feedbacks": ai_review.file_feedbacks,
        "issues": [
            {"tool": i.tool, "severity": i.severity, "message": i.message, "line": i.line}
            for r in analysis_results
            for i in r.issues
        ],
    }


def _extract_commit_message(event: str, data: dict) -> str:
    """Extract the commit or PR message from the webhook payload."""
    if event == "pull_request":
        pr = data.get("pull_request", {})
        title = pr.get("title", "")
        body = pr.get("body") or ""
        return f"{title}\n\n{body}".strip() if body else title
    head = data.get("head_commit")
    if head:
        return head.get("message", "")
    commits = data.get("commits", [])
    return commits[-1]["message"] if commits else ""


async def _run_static_analysis(files: list[ChangedFile]) -> list[StaticAnalysisResult]:
    """Run pylint/flake8/bandit on Python files; returns empty list for non-Python repos."""
    python_files = [f for f in files if f.filename.endswith(".py")]
    return await asyncio.to_thread(
        lambda: [analyze_file(f.filename, f.content) for f in python_files]
    )


def _build_notify_tasks(  # pylint: disable=too-many-positional-arguments
    repo_config,
    repo_name, commit_sha, pr_number,
    owner_token, score_result, analysis_results, ai_review,
):
    """Build coroutine task list for all active notification channels."""
    tasks = []
    names = []

    # Telegram (리포 설정 우선, 없으면 global fallback)
    tg_chat_id = (repo_config.notify_chat_id if repo_config else None) or settings.telegram_chat_id
    tasks.append(send_analysis_result(
        bot_token=settings.telegram_bot_token,
        chat_id=tg_chat_id,
        repo_name=repo_name,
        commit_sha=commit_sha,
        score_result=score_result,
        analysis_results=analysis_results,
        pr_number=pr_number,
        ai_review=ai_review,
    ))
    names.append("telegram")

    # Discord
    if repo_config and repo_config.discord_webhook_url:
        tasks.append(send_discord_notification(
            webhook_url=repo_config.discord_webhook_url,
            repo_name=repo_name,
            commit_sha=commit_sha,
            score_result=score_result,
            analysis_results=analysis_results,
            pr_number=pr_number,
            ai_review=ai_review,
        ))
        names.append("discord")

    # Slack
    if repo_config and repo_config.slack_webhook_url:
        tasks.append(send_slack_notification(
            webhook_url=repo_config.slack_webhook_url,
            repo_name=repo_name,
            commit_sha=commit_sha,
            score_result=score_result,
            analysis_results=analysis_results,
            pr_number=pr_number,
            ai_review=ai_review,
        ))
        names.append("slack")

    # Generic Webhook
    if repo_config and repo_config.custom_webhook_url:
        tasks.append(send_webhook_notification(
            webhook_url=repo_config.custom_webhook_url,
            repo_name=repo_name,
            commit_sha=commit_sha,
            score_result=score_result,
            analysis_results=analysis_results,
            pr_number=pr_number,
            ai_review=ai_review,
        ))
        names.append("webhook")

    # Email
    if repo_config and repo_config.email_recipients and settings.smtp_host:
        tasks.append(send_email_notification(
            recipients=repo_config.email_recipients,
            repo_name=repo_name,
            commit_sha=commit_sha,
            score_result=score_result,
            analysis_results=analysis_results,
            pr_number=pr_number,
            ai_review=ai_review,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_pass=settings.smtp_pass,
        ))
        names.append("email")

    # n8n
    if repo_config and repo_config.n8n_webhook_url:
        tasks.append(notify_n8n(
            webhook_url=repo_config.n8n_webhook_url,
            repo_full_name=repo_name,
            commit_sha=commit_sha,
            pr_number=pr_number,
            score_result=score_result,
        ))
        names.append("n8n")

    return tasks, names


def _extract_event_metadata(event: str, data: dict) -> tuple[str, str, str, int | None]:
    """Webhook 페이로드에서 repo_name, commit_sha, commit_message, pr_number를 추출한다."""
    repo_name: str = data["repository"]["full_name"]
    commit_message = _extract_commit_message(event, data)
    if event == "pull_request":
        pr_number: int | None = data["number"]
        commit_sha: str = data["pull_request"]["head"]["sha"]
    else:
        pr_number = None
        commit_sha = data["after"]
    return repo_name, commit_sha, commit_message, pr_number


def _ensure_repo(db: Session, repo_name: str, commit_sha: str) -> tuple[Repository, str] | None:
    """리포를 조회·등록하고 owner token을 결정한다. SHA 중복이면 None을 반환한다."""
    owner_token: str = settings.github_token
    repo = db.query(Repository).filter_by(full_name=repo_name).first()
    if not repo:
        repo = Repository(full_name=repo_name, telegram_chat_id=settings.telegram_chat_id)
        db.add(repo)
        db.commit()
    if repo.owner and repo.owner.plaintext_token:
        owner_token = repo.owner.plaintext_token
    if db.query(Analysis).filter_by(commit_sha=commit_sha, repo_id=repo.id).first():
        logger.info("Commit %s already analyzed, skipping", commit_sha)
        return None
    return repo, owner_token


async def _save_and_gate(
    db: Session,
    repo_name: str,
    commit_sha: str,
    commit_message: str,
    pr_number: int | None,
    owner_token: str,
    analysis_results: list,
    ai_review,
    score_result,
):
    """Analysis를 DB에 저장하고 Gate Engine을 실행한다. repo_config를 반환한다."""
    repo = db.query(Repository).filter_by(full_name=repo_name).first()
    if repo is None:
        logger.warning("Repository not found in second session: %s", repo_name)
        return None
    analysis = Analysis(
        repo_id=repo.id,
        commit_sha=commit_sha,
        commit_message=commit_message,
        pr_number=pr_number,
        score=score_result.total,
        grade=score_result.grade,
        result=_build_result_dict(
            ai_review, score_result, analysis_results,
            source="pr" if pr_number else "push",
        ),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    try:
        repo_config = get_repo_config(db, repo_name)
    except (SQLAlchemyError, KeyError):
        logger.warning("Failed to load repo config for %s, using defaults", repo_name)
        repo_config = None
    if pr_number is not None:
        try:
            await run_gate_check(
                repo_name=repo_name,
                pr_number=pr_number,
                analysis_id=analysis.id,
                result=analysis.result,
                github_token=owner_token,
                db=db,
                config=repo_config,
            )
        except Exception as exc:  # noqa: BLE001 — gate check는 httpx·DB·기타 다양한 예외 발생 가능
            logger.error("Gate check failed: %s", exc)
    return repo_config


async def run_analysis_pipeline(event: str, data: dict) -> None:
    """Webhook 이벤트를 받아 정적분석 + AI 리뷰 → 점수 → Gate → 알림 파이프라인을 실행한다.

    Args:
        event: GitHub 이벤트 타입 ("push" | "pull_request")
        data:  GitHub Webhook JSON 페이로드

    흐름:
        1. repo 등록 / SHA 중복 체크 (중복이면 즉시 반환)
        2. 변경 파일 수집 (get_pr_files / get_push_files)
        3. asyncio.gather — 정적분석(pylint·flake8·bandit) + AI 리뷰 병렬 실행
        4. 점수·등급 계산 → Analysis DB 저장
        5. run_gate_check (PR 이벤트만) — Review Comment·Approve·Auto Merge
        6. _build_notify_tasks → Telegram·Discord·Slack·Webhook·Email·n8n 알림
    """
    try:
        repo_name, commit_sha, commit_message, pr_number = _extract_event_metadata(event, data)

        with SessionLocal() as db:
            result = _ensure_repo(db, repo_name, commit_sha)
            if result is None:
                return
            _, owner_token = result

        if event == "pull_request":
            files = get_pr_files(owner_token, repo_name, pr_number)
        else:
            files = get_push_files(owner_token, repo_name, commit_sha)

        if not files:
            logger.info("No changed files in %s @ %s", repo_name, commit_sha)
            return

        patches = [(f.filename, f.patch) for f in files if f.patch]
        analysis_results, ai_review = await asyncio.gather(
            _run_static_analysis(files),
            review_code(settings.anthropic_api_key, commit_message, patches),
        )
        score_result = calculate_score(analysis_results, ai_review=ai_review)

        with SessionLocal() as db:
            repo_config = await _save_and_gate(
                db, repo_name, commit_sha, commit_message, pr_number,
                owner_token, analysis_results, ai_review, score_result,
            )

        notify_tasks, task_names = _build_notify_tasks(
            repo_config=repo_config,
            repo_name=repo_name,
            commit_sha=commit_sha,
            pr_number=pr_number,
            owner_token=owner_token,
            score_result=score_result,
            analysis_results=analysis_results,
            ai_review=ai_review,
        )
        results = await asyncio.gather(*notify_tasks, return_exceptions=True)
        for idx, exc in enumerate(results):
            if isinstance(exc, Exception):
                name = task_names[idx] if idx < len(task_names) else "unknown"
                logger.error("Notification [%s] failed: %s", name, exc,
                             exc_info=(type(exc), exc, exc.__traceback__))

    except Exception:  # noqa: BLE001 — 파이프라인 최상위 방어 — 모든 예외를 로그로 기록하고 종료
        logger.exception("Analysis pipeline failed for event=%s", event)
