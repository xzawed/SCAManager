"""Analysis pipeline — orchestrates static analysis, AI review, scoring, and notifications."""
import asyncio
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.config import settings
from src.shared.log_safety import sanitize_for_log
from src.shared.stage_metrics import stage_timer
from src.github_client.diff import get_pr_files, get_push_files, ChangedFile
from src.analyzer.io.static import analyze_file, StaticAnalysisResult
from src.analyzer.io.ai_review import review_code
from src.scorer.calculator import calculate_score
from src.models.repository import Repository
from src.models.analysis import Analysis
from src.gate.engine import run_gate_check
from src.config_manager.manager import get_repo_config
# src.notifier 임포트 시 각 채널 모듈이 자동으로 REGISTRY 에 등록됨
import src.notifier  # noqa: F401 — 자동 등록 트리거  # pylint: disable=unused-import
from src.notifier.registry import NotifyContext, REGISTRY
from src.repositories import repository_repo, analysis_repo

logger = logging.getLogger(__name__)


@dataclass
class _AnalysisSaveParams:  # pylint: disable=too-many-instance-attributes
    """_save_and_gate에 전달하는 분석 저장 파라미터 묶음."""

    repo_name: str
    commit_sha: str
    commit_message: str
    pr_number: int | None
    owner_token: str
    analysis_results: list
    ai_review: object  # AiReviewResult
    score_result: object  # ScoreResult
    author_login: str | None = None


# ---------------------------------------------------------------------------
# Notifier 채널 구현체는 Phase S.3-E 이후 src/notifier/*.py 로 이관됨.
# `import src.notifier` 가 모듈 로드 시 각 채널의 `register()` 를 트리거해
# REGISTRY 에 자동 등록된다. 새 채널 추가 시:
#   1. src/notifier/<channel>.py 에 클래스 작성 + register() 호출
#   2. src/notifier/__init__.py 에 `import src.notifier.<channel>` 1줄
# ---------------------------------------------------------------------------


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


def _extract_author_login(event_type: str, data: dict) -> str | None:
    """Webhook 페이로드에서 커밋 작성자 GitHub 로그인을 추출한다.
    Extract the commit author's GitHub login from the webhook payload.

    PR: data["pull_request"]["user"]["login"]
    push: data["head_commit"]["author"]["username"]
    키 누락 시 None 반환 — 조용히 실패.
    On missing keys, returns None silently.
    """
    if event_type == "pull_request":
        return (data.get("pull_request") or {}).get("user", {}).get("login")
    head = data.get("head_commit") or {}
    return (head.get("author") or {}).get("username")


async def _run_static_analysis(files: list[ChangedFile]) -> list[StaticAnalysisResult]:
    """Run registered analyzers on all changed files; each Analyzer filters by language."""
    return await asyncio.to_thread(
        lambda: [analyze_file(f.filename, f.content) for f in files]
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
    except SQLAlchemyError:
        # Phase H PR-6A: logger.exception 으로 stack trace 보존
        logger.exception(
            "pr_number update failed (sha=%s, pr=#%d)", commit_sha, pr_number,
        )
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
    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # Phase 2: logger.exception 으로 stack trace 보존 — PR #105 silent skip
        # 사고에서 line 211 의 `logger.error(... %s, exc)` 가 메시지만 남겨 Sentry/
        # Railway 로그에서 원인 추적 불가능했던 문제 해결.
        # Phase 2: use logger.exception so the full traceback is captured in Sentry/
        # Railway logs (the previous `logger.error` only left the exc message,
        # making the PR #105 silent-skip incident unreproducible from logs).
        logger.exception(
            "Re-gate check failed (pr=#%d, sha=%s)", pr_number, commit_sha[:8],
        )


async def _save_and_gate(db: Session, params: _AnalysisSaveParams):
    """Analysis를 DB에 저장하고 Gate Engine을 실행한다.

    Returns:
        (repo_config, analysis_id, result_dict) 튜플.
        중복 커밋이면 (repo_config_or_None, None, None).
    """
    repo = repository_repo.find_by_full_name(db, params.repo_name)
    if repo is None:
        logger.warning("Repository not found in second session: %s", params.repo_name)
        return None, None, None
    # 멱등성 재확인 — 동시 Webhook 전달로 인한 중복 Analysis 삽입 방지 (TOCTOU 완화)
    # Idempotency re-check — defends against concurrent webhooks racing past the first dedup.
    existing = analysis_repo.find_by_sha(db, params.commit_sha, repo.id)
    if existing is not None:
        logger.info("Commit %s already saved (concurrent insert detected), skipping", params.commit_sha)
        # Phase 2 race fix (PR #105 silent skip 사고 대응):
        # push 이벤트가 먼저 통과해 pr_number=None 으로 저장되고, 그 사이 이 PR
        # 이벤트가 도착하면 1차 dedup → _regate_pr_if_needed 경로로 진입한다.
        # 그러나 두 이벤트가 거의 동시에 도착해 둘 다 1차 dedup 통과 → 분석을
        # 실행 → 2차 dedup 에서 PR 이벤트만 여기로 진입할 수 있다. 이때 gate 가
        # 실행되지 않으면 PR #105 처럼 코멘트/머지 모두 누락된다 (silent skip).
        # 보정: pr_number 가 비어있는 기존 Analysis 에 현재 PR 번호 부여 후 gate
        # 재실행. _regate_pr_if_needed 와 동일한 의미론.
        # Race fix: when an existing Analysis lacks pr_number and this is a PR event,
        # patch pr_number then re-run the gate (matches `_regate_pr_if_needed`).
        try:
            repo_config = get_repo_config(db, params.repo_name)
        except (SQLAlchemyError, KeyError):
            repo_config = None
        if params.pr_number is not None and existing.pr_number is None:
            try:
                existing.pr_number = params.pr_number
                db.commit()
                await run_gate_check(
                    repo_name=params.repo_name,
                    pr_number=params.pr_number,
                    analysis_id=existing.id,
                    result=existing.result,
                    github_token=params.owner_token,
                    db=db,
                    config=repo_config,
                )
                logger.info(
                    "Race-recovered: PR #%d re-gated on concurrent existing Analysis %d (sha=%s)",
                    params.pr_number, existing.id, params.commit_sha[:8],
                )
            except SQLAlchemyError:
                # Phase H PR-6A: logger.exception 으로 stack trace 보존
                logger.exception(
                    "Race-recovery pr_number commit failed (sha=%s, pr=#%d)",
                    params.commit_sha, params.pr_number,
                )
                db.rollback()
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                # logger.exception 으로 stack trace 보존 — Sentry/Railway 로그에서 진짜 원인 추적 가능
                # logger.exception preserves the stack trace for Sentry/Railway log triage
                logger.exception(
                    "Race-recovery gate check failed (pr=#%d, sha=%s)",
                    params.pr_number, params.commit_sha[:8],
                )
        return repo_config, None, None
    result_dict = build_analysis_result_dict(
        params.ai_review, params.score_result, params.analysis_results,
        source="pr" if params.pr_number else "push",
    )
    analysis = analysis_repo.save_new(db, Analysis(
        repo_id=repo.id,
        commit_sha=params.commit_sha,
        commit_message=params.commit_message,
        pr_number=params.pr_number,
        score=params.score_result.total,
        grade=params.score_result.grade,
        result=result_dict,
        author_login=params.author_login,
    ))
    analysis_id = analysis.id
    try:
        repo_config = get_repo_config(db, params.repo_name)
    except (SQLAlchemyError, KeyError):
        logger.warning("Failed to load repo config for %s, using defaults", params.repo_name)
        repo_config = None
    if params.pr_number is not None:
        try:
            await run_gate_check(
                repo_name=params.repo_name,
                pr_number=params.pr_number,
                analysis_id=analysis_id,
                result=result_dict,
                github_token=params.owner_token,
                db=db,
                config=repo_config,
            )
        except (httpx.HTTPError, SQLAlchemyError, KeyError, ValueError, OSError):
            # Phase H PR-6A: logger.exception 으로 stack trace 보존
            logger.exception("Gate check failed")
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            logger.error("Gate check unexpected error: %s", exc, exc_info=True)
    return repo_config, analysis_id, result_dict


def _collect_files(
    event: str,
    owner_token: str,
    repo_name: str,
    commit_sha: str,
    pr_number: int | None,
) -> list:
    """이벤트 타입에 따라 변경 파일 목록을 수집한다."""
    if event == "pull_request":
        return get_pr_files(owner_token, repo_name, pr_number)
    return get_push_files(owner_token, repo_name, commit_sha)


async def _send_notifications(notify_tasks: list, task_names: list[str]) -> None:
    """알림 채널들을 병렬 실행하고 실패를 로그로 기록한다."""
    results = await asyncio.gather(*notify_tasks, return_exceptions=True)
    for idx, exc in enumerate(results):
        if isinstance(exc, Exception):
            name = task_names[idx] if idx < len(task_names) else "unknown"
            logger.error("Notification [%s] failed: %s", name, exc,
                         exc_info=(type(exc), exc, exc.__traceback__))


async def run_analysis_pipeline(event: str, data: dict) -> None:  # pylint: disable=too-many-locals
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

    Phase E.2c — 주요 단계에 `stage_timer` 추가. 구조화된 duration_ms/status 로그로
    실측 지연 추적.
    """
    try:
        with stage_timer("pipeline_total", event=event):
            repo_name, commit_sha, commit_message, pr_number = _extract_event_metadata(event, data)
            # user-controlled webhook 입력이므로 로그 인젝션 방어 (CLAUDE.md 규약)
            repo_log = sanitize_for_log(repo_name)
            pr_head_ref = (
                data.get("pull_request", {}).get("head", {}).get("ref")
                if event == "pull_request" else None
            )

            with SessionLocal() as db:
                ensure_result = _ensure_repo(db, repo_name, commit_sha)
                if ensure_result is None:
                    if event == "pull_request" and pr_number is not None:
                        await _regate_pr_if_needed(db, repo_name, commit_sha, pr_number)
                    return
                _, owner_token = ensure_result

            with stage_timer("collect_files", repo=repo_log) as ctx:
                # Phase H PR-3A: PyGithub 동기 I/O 를 별도 스레드로 격리
                # _collect_files 내부의 PyGithub 호출은 sync HTTP I/O — async
                # 컨텍스트에서 직접 실행 시 이벤트 루프 블록 (20파일 PR 시 5-15s).
                # asyncio.to_thread 로 wrap 해 다른 BackgroundTask 처리를 막지 않음.
                # Phase H PR-3A: offload PyGithub sync I/O to a worker thread.
                # Direct calls block the event loop (~5-15s on 20-file PRs);
                # asyncio.to_thread keeps other BackgroundTasks responsive.
                files = await asyncio.to_thread(
                    _collect_files, event, owner_token, repo_name, commit_sha, pr_number,
                )
                ctx["file_count"] = len(files)

            if not files:
                logger.info("No changed files in %s @ %s", repo_log, commit_sha)
                return

            patches = [(f.filename, f.patch) for f in files if f.patch]
            with stage_timer("analyze", repo=repo_log) as ctx:
                analysis_results, ai_review = await asyncio.gather(
                    _run_static_analysis(files),
                    review_code(settings.anthropic_api_key, commit_message, patches),
                )
                ctx["file_count"] = len(analysis_results)
                ctx["issue_count"] = sum(len(r.issues) for r in analysis_results)

            with stage_timer("score_and_save", repo=repo_log) as ctx:
                score_result = calculate_score(analysis_results, ai_review=ai_review)
                ctx["score"] = score_result.total
                save_params = _AnalysisSaveParams(
                    repo_name=repo_name,
                    commit_sha=commit_sha,
                    commit_message=commit_message,
                    pr_number=pr_number,
                    owner_token=owner_token,
                    analysis_results=analysis_results,
                    ai_review=ai_review,
                    score_result=score_result,
                    author_login=_extract_author_login(event, data),
                )
                with SessionLocal() as db:
                    repo_config, analysis_id, result_dict = await _save_and_gate(db, save_params)

            # Phase H PR-2A: race-recovery 또는 repo 누락 시 notify skip
            # `_save_and_gate` 가 result_dict=None 을 반환하면 두 가지 경우다:
            #   (1) repo 가 두 번째 세션에서 사라짐 — 알림 의미 없음
            #   (2) 동시 webhook race 로 기존 Analysis 가 이미 알림을 발송함 —
            #       중복 알림 방지 + result_dict=None 으로 인한 silent KeyError 차단
            # `analysis_id` 는 실 운영에서 항상 int 이지만 단위 테스트의 mock db
            # 에서는 refresh() 가 동작하지 않아 None 일 수 있음 — race-recovery
            # 시그널은 두 값 동시 None 인 `result_dict is None` 으로 판정.
            # Phase H PR-2A: skip notify on race-recovery or missing repo.
            # `result_dict is None` is the canonical race-recovery signal — only
            # set when `_save_and_gate` early-returned without building the dict.
            # `analysis_id is None` cannot be used alone because mock-DB tests
            # leave it None (refresh() no-op) even on the normal path.
            if result_dict is None:
                logger.info(
                    "Race-recovery or repo missing for %s @ %s — skipping notify stage",
                    repo_log, commit_sha,
                )
                return

            with stage_timer("notify", repo=repo_log) as ctx:
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
                ctx["channel_count"] = len(task_names)
                await _send_notifications(notify_tasks, task_names)

    except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.exception("Analysis pipeline failed for event=%s", event)
