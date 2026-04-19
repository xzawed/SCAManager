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
from src.notifier.github_commit_comment import post_commit_comment
from src.notifier.github_issue import create_low_score_issue
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.gate.engine import run_gate_check
from src.notifier.n8n import notify_n8n
from src.notifier.discord import send_discord_notification
from src.notifier.slack import send_slack_notification
from src.notifier.webhook import send_webhook_notification
from src.notifier.email import send_email_notification
from src.config_manager.manager import get_repo_config
from src.notifier.registry import NotifyContext, REGISTRY, register
from src.repositories import repository_repo, analysis_repo
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 알림 채널 구현체 — Notifier 프로토콜 구현 + 레지스트리 등록
# 새 채널 추가: 클래스 하나 작성 후 register() 호출만으로 완성.
# ---------------------------------------------------------------------------
# pylint: disable=missing-function-docstring

class _TelegramChannel:
    name = "telegram"

    def is_enabled(self, ctx: NotifyContext) -> bool:  # pylint: disable=unused-argument
        return True  # 항상 활성 (global fallback 포함)

    async def send(self, ctx: NotifyContext) -> None:
        chat_id = (ctx.config.notify_chat_id if ctx.config else None) or settings.telegram_chat_id
        await send_analysis_result(
            bot_token=settings.telegram_bot_token,
            chat_id=chat_id,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
        )


class _DiscordChannel:
    name = "discord"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        return bool(ctx.config and ctx.config.discord_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        await send_discord_notification(
            webhook_url=ctx.config.discord_webhook_url,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
        )


class _SlackChannel:
    name = "slack"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        return bool(ctx.config and ctx.config.slack_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        await send_slack_notification(
            webhook_url=ctx.config.slack_webhook_url,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
        )


class _WebhookChannel:
    name = "webhook"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        return bool(ctx.config and ctx.config.custom_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        await send_webhook_notification(
            webhook_url=ctx.config.custom_webhook_url,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
        )


class _EmailChannel:
    name = "email"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        return bool(ctx.config and ctx.config.email_recipients and settings.smtp_host)

    async def send(self, ctx: NotifyContext) -> None:
        await send_email_notification(
            recipients=ctx.config.email_recipients,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            score_result=ctx.score_result,
            analysis_results=ctx.analysis_results,
            pr_number=ctx.pr_number,
            ai_review=ctx.ai_review,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_user=settings.smtp_user,
            smtp_pass=settings.smtp_pass,
        )


class _N8nChannel:
    name = "n8n"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        return bool(ctx.config and ctx.config.n8n_webhook_url)

    async def send(self, ctx: NotifyContext) -> None:
        await notify_n8n(
            webhook_url=ctx.config.n8n_webhook_url,
            repo_full_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            pr_number=ctx.pr_number,
            score_result=ctx.score_result,
            n8n_secret=settings.n8n_webhook_secret,
        )


class _CommitCommentChannel:
    name = "commit_comment"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        return bool(
            ctx.config and ctx.config.commit_comment
            and ctx.pr_number is None  # push 이벤트 전용
            and ctx.result_dict
        )

    async def send(self, ctx: NotifyContext) -> None:
        await post_commit_comment(
            github_token=ctx.owner_token,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            result=ctx.result_dict,
        )


class _IssueChannel:
    name = "create_issue"

    def is_enabled(self, ctx: NotifyContext) -> bool:
        if not (ctx.config and ctx.config.create_issue and ctx.result_dict):
            return False
        is_bot_pr = ctx.pr_head_ref and ctx.pr_head_ref.startswith("claude-fix/")
        if is_bot_pr:
            return False
        has_bandit_high = any(
            i.get("severity") == "HIGH" and i.get("tool") == "bandit"
            for i in (ctx.result_dict.get("issues") or [])
        )
        return ctx.score_result.total < ctx.config.reject_threshold or has_bandit_high

    async def send(self, ctx: NotifyContext) -> None:
        await create_low_score_issue(
            github_token=ctx.owner_token,
            repo_name=ctx.repo_name,
            commit_sha=ctx.commit_sha,
            analysis_id=ctx.analysis_id,
            result=ctx.result_dict,
        )


# 모듈 로드 시 채널 등록 (순서 = 우선순위)
for _ch in [
    _TelegramChannel(), _DiscordChannel(), _SlackChannel(),
    _WebhookChannel(), _EmailChannel(), _N8nChannel(),
    _CommitCommentChannel(), _IssueChannel(),
]:
    register(_ch)
del _ch  # 루프 변수 cleanup


def build_analysis_result_dict(
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


def build_notification_tasks(  # pylint: disable=too-many-positional-arguments,too-many-arguments
    repo_config,
    repo_name, commit_sha, pr_number,
    owner_token, score_result, analysis_results, ai_review,
    analysis_id=None, result_dict=None,
    pr_head_ref=None,
):
    """Build coroutine task list for all active notification channels.

    채널을 추가하려면 Notifier 프로토콜을 구현하고 register()를 호출하면 됩니다.
    """
    ctx = NotifyContext(
        repo_name=repo_name, commit_sha=commit_sha, pr_number=pr_number,
        score_result=score_result, analysis_results=analysis_results, ai_review=ai_review,
        owner_token=owner_token, analysis_id=analysis_id, result_dict=result_dict,
        pr_head_ref=pr_head_ref, config=repo_config,
    )
    tasks = []
    names = []
    for notifier in REGISTRY:
        if notifier.is_enabled(ctx):
            tasks.append(notifier.send(ctx))
            names.append(notifier.name)
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
    repo = repository_repo.find_by_full_name(db, repo_name)
    if not repo:
        repo = repository_repo.save_new(
            db, Repository(full_name=repo_name, telegram_chat_id=settings.telegram_chat_id)
        )
        db.commit()
    if repo.owner and repo.owner.plaintext_token:
        owner_token = repo.owner.plaintext_token
    if analysis_repo.find_by_sha(db, commit_sha, repo.id):
        logger.info("Commit %s already analyzed, skipping", commit_sha)
        return None
    return repo, owner_token


async def _regate_pr_if_needed(
    db: Session, repo_name: str, commit_sha: str, pr_number: int
) -> None:
    """push 이후 도착한 PR 이벤트에서 기존 Analysis에 pr_number를 부여하고 gate만 재실행한다.

    동일 SHA Analysis가 pr_number=None으로 저장된 경우(push 이벤트가 PR보다 먼저 도착),
    PR 이벤트 수신 시 분석을 재실행하지 않고 gate 경로만 진입한다.
    pr_number가 이미 같으면 아무 작업도 하지 않는다.
    """
    repo = repository_repo.find_by_full_name(db, repo_name)
    if repo is None:
        return
    existing = analysis_repo.find_by_sha(db, commit_sha, repo.id)
    if existing is None or existing.pr_number == pr_number:
        return
    try:
        existing.pr_number = pr_number
        db.commit()
    except SQLAlchemyError as exc:
        logger.error("pr_number update failed (sha=%s, pr=#%d): %s", commit_sha, pr_number, exc)
        db.rollback()
        return
    owner_token: str = settings.github_token
    if repo.owner and repo.owner.plaintext_token:
        owner_token = repo.owner.plaintext_token
    try:
        await run_gate_check(
            repo_name=repo_name,
            pr_number=pr_number,
            analysis_id=existing.id,
            result=existing.result,
            github_token=owner_token,
            db=db,
        )
        logger.info("Re-gated PR #%d for existing Analysis %d (sha=%s)",
                    pr_number, existing.id, commit_sha[:8])
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Re-gate check failed: %s", exc)


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
    """Analysis를 DB에 저장하고 Gate Engine을 실행한다.

    Returns:
        (repo_config, analysis_id, result_dict) 튜플.
        중복 커밋이면 (repo_config_or_None, None, None).
    """
    repo = repository_repo.find_by_full_name(db, repo_name)
    if repo is None:
        logger.warning("Repository not found in second session: %s", repo_name)
        return None, None, None
    # 멱등성 재확인 — 동시 Webhook 전달로 인한 중복 Analysis 삽입 방지 (TOCTOU 완화)
    if analysis_repo.find_by_sha(db, commit_sha, repo.id):
        logger.info("Commit %s already saved (concurrent insert detected), skipping", commit_sha)
        try:
            return get_repo_config(db, repo_name), None, None
        except (SQLAlchemyError, KeyError):
            return None, None, None
    result_dict = build_analysis_result_dict(
        ai_review, score_result, analysis_results,
        source="pr" if pr_number else "push",
    )
    analysis = analysis_repo.save_new(db, Analysis(
        repo_id=repo.id,
        commit_sha=commit_sha,
        commit_message=commit_message,
        pr_number=pr_number,
        score=score_result.total,
        grade=score_result.grade,
        result=result_dict,
    ))
    analysis_id = analysis.id
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
                analysis_id=analysis_id,
                result=result_dict,
                github_token=owner_token,
                db=db,
                config=repo_config,
            )
        except Exception as exc:  # noqa: BLE001 — gate check는 httpx·DB·기타 다양한 예외 발생 가능
            logger.error("Gate check failed: %s", exc)
    return repo_config, analysis_id, result_dict


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
        6. build_notification_tasks → Telegram·Discord·Slack·Webhook·Email·n8n 알림
    """
    try:
        repo_name, commit_sha, commit_message, pr_number = _extract_event_metadata(event, data)
        pr_head_ref = (
            data.get("pull_request", {}).get("head", {}).get("ref")
            if event == "pull_request" else None
        )

        with SessionLocal() as db:
            result = _ensure_repo(db, repo_name, commit_sha)
            if result is None:
                if event == "pull_request" and pr_number is not None:
                    await _regate_pr_if_needed(db, repo_name, commit_sha, pr_number)
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
            repo_config, analysis_id, result_dict = await _save_and_gate(
                db, repo_name, commit_sha, commit_message, pr_number,
                owner_token, analysis_results, ai_review, score_result,
            )

        notify_tasks, task_names = build_notification_tasks(
            repo_config=repo_config,
            repo_name=repo_name,
            commit_sha=commit_sha,
            pr_number=pr_number,
            owner_token=owner_token,
            score_result=score_result,
            analysis_results=analysis_results,
            ai_review=ai_review,
            analysis_id=analysis_id,
            result_dict=result_dict,
            pr_head_ref=pr_head_ref,
        )
        results = await asyncio.gather(*notify_tasks, return_exceptions=True)
        for idx, exc in enumerate(results):
            if isinstance(exc, Exception):
                name = task_names[idx] if idx < len(task_names) else "unknown"
                logger.error("Notification [%s] failed: %s", name, exc,
                             exc_info=(type(exc), exc, exc.__traceback__))

    except Exception:  # noqa: BLE001 — 파이프라인 최상위 방어 — 모든 예외를 로그로 기록하고 종료
        logger.exception("Analysis pipeline failed for event=%s", event)
