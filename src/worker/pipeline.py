"""Analysis pipeline — orchestrates static analysis, AI review, scoring, and notifications."""
import asyncio
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.database import WorkerSessionLocal as SessionLocal
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
from src.gate._common import ai_review_failed
from src.config_manager.manager import get_repo_config
# src.notifier 임포트 시 각 채널 모듈이 자동으로 REGISTRY 에 등록됨
import src.notifier  # noqa: F401 — 자동 등록 트리거  # pylint: disable=unused-import
from src.notifier.registry import NotifyContext, REGISTRY
from src.repositories import repository_repo, analysis_repo

logger = logging.getLogger(__name__)

# 정적 분석 전체 타임아웃(deadline) 단일 출처 (초) — 초과 시 완료된 파일 부분결과 보존 +
# incomplete 신호 반환(auto-merge 차단), AI 리뷰는 계속 진행
# Single source of truth for the static-analysis deadline (seconds) — on overrun keeps the
# partial results of completed files and returns an incomplete flag (blocks auto-merge); AI review continues
PIPELINE_ANALYSIS_TIMEOUT = 60


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
    # 정적분석 타임아웃 등 불완전 분석 여부 — True 시 result 에 마커 + auto-merge 차단
    # Static analysis incomplete (e.g. timeout) — when True, marks result + blocks auto-merge
    static_incomplete: bool = False


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
        # C22: diff 절단 마커 — auto-merge/auto-approve 차단 (static_analysis_incomplete 대칭).
        # getattr 기본 False: truncated 미보유 구 레코드/더블 안전.
        # C22: diff-truncation marker — blocks auto-merge/approve (mirrors static_analysis_incomplete).
        # getattr default False keeps legacy records/doubles without the field safe.
        "ai_review_truncated": bool(getattr(ai_review, "truncated", False)),
        "ai_summary": ai_review.summary,
        "ai_suggestions": ai_review.suggestions,
        "commit_message_feedback": ai_review.commit_message_feedback,
        "code_quality_feedback": ai_review.code_quality_feedback,
        "security_feedback": ai_review.security_feedback,
        "direction_feedback": ai_review.direction_feedback,
        "test_feedback": ai_review.test_feedback,
        "file_feedbacks": ai_review.file_feedbacks,
        "issues": [
            # category / language 추가 — 향후 dashboard 에서 언어별·카테고리별 사후 분석 가능
            # category / language added so future dashboards can slice by language/category
            {
                "tool": i.tool,
                "severity": i.severity,
                "message": i.message,
                "line": i.line,
                "category": i.category,
                "language": i.language,
            }
            for r in analysis_results
            for i in r.issues
        ],
    }


def _persisted_score_is_unreliable(result_dict: dict) -> bool:
    """score/grade 컬럼을 NULL 로 저장해야 하는지 판정한다 (analytics 집계 오염 방지).
    Decide whether score/grade must be NULL-persisted (so aggregations exclude this row).

    NULL 대상 = AI 리뷰 genuine 실패(`api_error`/`parse_error`) 한정 — `ai_review_failed`
    (hook #25/#814 대칭). 실패 시 인플레 기본 점수(`_default_result` 17/17/7 → ~89/B)가
    저장돼 집계를 오염시키므로 NULL. `no_api_key`/`empty_diff`(의도적 미수행)는
    `ai_review_failed=False` → 점수 유지(회귀 방지).

    🔴 입력-diff 절단(`ai_review_truncated`)은 NULL 대상에서 **제외**한다(C22 분리):
    절단 리뷰는 status="success" 이고 점수의 대부분(code_quality/security)은 전체 파일 정적분석
    기반이라 신뢰할 수 있다. diff 가 `MAX_DIFF_CHARS`(16,000자)를 넘는 대형 commit/PR 의 절반이
    절단되는데, 이를 전부 NULL-persist 하면 대시보드/리더보드에서 점수가 통째로 사라진다
    (운영 DB 실측: 6월 NULL 256건 다수가 절단형, 일 성공률 24~57% 로 급락). 절단 시
    auto-merge/auto-approve 차단은 result dict 의 `ai_review_truncated` 마커를 직접 읽는 #885
    가드(`static_analysis_incomplete` 대칭)가 담당 — 점수 컬럼 NULL 여부와 무관하므로 안전성 영향 0.
    대시보드/리더보드 집계(`func.avg`·leaderboard)가 NULL 을 자연 제외하므로 오염 차단(쿼리 변경 0).

    NULL target = a genuine AI-review failure (api_error/parse_error) only. Input-diff truncation is
    EXCLUDED: the score is mostly full-file static analysis (reliable), and NULLing ~half of
    large-diff analyses wiped scores off the dashboard. Auto-merge/approve still blocks on the
    `ai_review_truncated` marker (#885), independent of the score column. Intentional skips keep score.
    """
    return ai_review_failed(result_dict)


def _extract_commit_message(event: str, data: dict) -> str:
    """Extract the commit or PR message from the webhook payload."""
    if event == "pull_request":
        # pull_request 키가 present-but-None 일 수 있어 `or {}` 정규화 (PR #124 패턴)
        # pull_request key may be present-but-None — normalize with `or {}` (PR #124 pattern)
        pr = data.get("pull_request") or {}
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
        # user 키도 present-but-None 가능 — 한 단계 더 `or {}` 정규화 (PR #124 패턴)
        # user key may also be present-but-None — normalize one more level (PR #124 pattern)
        return ((data.get("pull_request") or {}).get("user") or {}).get("login")
    head = data.get("head_commit") or {}
    return (head.get("author") or {}).get("username")


def _extract_pr_head_ref(event: str, data: dict) -> str | None:
    """PR 이벤트에서 head 브랜치 ref 를 추출한다 (PR 외 이벤트는 None).
    Extract the head branch ref from a PR event (None for non-PR events).

    pull_request / head 키가 present-but-None 일 수 있어 `or {}` 정규화 (PR #124 패턴).
    pull_request / head keys may be present-but-None — normalize with `or {}` (PR #124 pattern).
    """
    if event != "pull_request":
        return None
    pr = data.get("pull_request") or {}
    return (pr.get("head") or {}).get("ref")


async def _run_static_analysis(
    files: list[ChangedFile], repo_config: object | None = None
) -> list[StaticAnalysisResult]:
    """Run registered analyzers on the given changed files in one worker thread.

    _run_static_with_timeout 가 파일별로 호출하며, 파일 단위 격리·deadline·실패 집계는
    호출측(_run_static_with_timeout)이 담당한다. 여기서는 동기 분석 루프만 to_thread 로 offload.
    Called per-file by _run_static_with_timeout; per-file isolation, deadline, and failure
    counting live in the caller. This only offloads the sync analysis loop to a thread.

    repo_config: RepoConfig 인스턴스 — disabled_tools 필터링에 사용.
    repo_config: RepoConfig instance — used for disabled_tools filtering.
    """
    return await asyncio.to_thread(
        lambda: [analyze_file(f.filename, f.content, repo_config=repo_config) for f in files]
    )


async def _run_static_with_timeout(
    files: list[ChangedFile], repo_config: object | None = None
) -> tuple[list[StaticAnalysisResult], bool]:
    """정적분석을 PIPELINE_ANALYSIS_TIMEOUT 초 deadline 으로 파일 단위 순차 실행한다.
    Run static analysis file-by-file under a PIPELINE_ANALYSIS_TIMEOUT-second deadline.

    각 파일을 독립 to_thread 로 순차 await 하므로 (1) subprocess 동시 폭주가 없고,
    (2) deadline 초과 시 그때까지 완료된 파일의 부분결과를 보존하며,
    (3) 타임아웃으로 고아가 되는 워커 스레드는 진행 중이던 단일 파일 1개로 한정된다
    (파일당 도구 subprocess timeout=STATIC_ANALYSIS_TIMEOUT 합산으로 bounded — 자연 종료).
    Each file runs in its own to_thread, awaited sequentially, so (1) there is no concurrent
    subprocess blow-up, (2) partial results of completed files are preserved on deadline, and
    (3) at most one in-flight file's worker thread can be orphaned on timeout (bounded by the
    sum of that file's per-tool subprocess timeouts).

    파일 단위 격리(Q2): 한 파일의 analyze_file 예외(디스크/encoding/tempfile 오류 등)는
    빈 StaticAnalysisResult 로 격리하고 다음 파일을 계속 분석한다 (배치/AI리뷰 미중단).
    Per-file isolation (Q2): a single file's analyze_file failure is isolated as an empty result
    and the loop continues — it does not abort the batch or AI review.

    Returns:
        (results, incomplete). incomplete=True 는 (a) deadline 초과, 또는 (b) 비어있지 않은
        배치의 모든 파일이 실패한 경우의 신호로, 부분/누락 분석이 "이슈 없음"(만점)으로 오인되어
        미분석 코드가 auto-merge 되는 것을 막는다. 일부 파일만 실패(나머지 정상 분석)는 Q2=A
        결정에 따라 incomplete 로 처리하지 않는다. AI 리뷰는 계속 진행.
        incomplete=True flags (a) a deadline overrun or (b) every file in a non-empty batch
        failing, so partial/missing analysis is not mistaken for "no issues" and auto-merged.
        A partial failure (some files analyzed) is NOT incomplete per the Q2=A decision.
    """
    results: list[StaticAnalysisResult] = []
    incomplete = False
    failed = 0
    loop = asyncio.get_running_loop()
    deadline = loop.time() + PIPELINE_ANALYSIS_TIMEOUT
    for f in files:
        remaining = deadline - loop.time()
        if remaining <= 0:
            incomplete = True
            logger.warning(
                "static analysis deadline (%ss) reached — %d/%d files analyzed, "
                "marking incomplete (auto-merge blocked, partial preserved)",
                PIPELINE_ANALYSIS_TIMEOUT, len(results), len(files),
            )
            break
        try:
            part = await asyncio.wait_for(
                _run_static_analysis([f], repo_config=repo_config),
                timeout=remaining,
            )
            results.extend(part)
        except asyncio.TimeoutError:
            incomplete = True
            logger.warning(
                "static analysis deadline (%ss) reached during %s — %d/%d files analyzed, "
                "marking incomplete (auto-merge blocked, partial preserved)",
                PIPELINE_ANALYSIS_TIMEOUT, f.filename, len(results), len(files),
            )
            break
        except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            # 파일 단위 격리(Q2) — 실패 파일은 빈 결과(이슈0)로 처리하고 다음 파일 진행
            # Per-file isolation (Q2) — failed file yields an empty result; loop continues
            failed += 1
            results.append(StaticAnalysisResult(filename=f.filename))
            logger.warning(
                "static analysis failed for %s — isolated as empty result",
                f.filename, exc_info=True,
            )
    # 안전망: 비어있지 않은 배치의 모든 파일이 예외 실패 → 실 분석 0건 → 미분석 코드
    # auto-merge 차단(fail-closed). 변경 전 동작(파일 예외 시 파이프라인 abort)이 Q2=A 격리로
    # 바뀌며 생길 수 있는 전량-실패 fail-open 회귀를 막는다.
    # Safety net: every file in a non-empty batch failed → zero real analysis → block auto-merge
    # of unanalyzed code (fail-closed). Prevents the total-failure fail-open regression that Q2=A
    # isolation could introduce versus the previous abort-on-exception behavior.
    if files and failed == len(files):
        incomplete = True
        logger.warning(
            "all %d files failed static analysis — marking incomplete (auto-merge blocked)",
            len(files),
        )
    # 도구 subprocess 타임아웃(per-tool 30s, 파일 deadline 60s 미트립)으로 일부 분석이 누락된
    # 파일이 있으면 incomplete 로 전파 — 무음 폐기된 이슈가 만점 인플레로 auto-merge 되는 것 차단(#7).
    # Any file with a tool subprocess-timeout (per-tool 30s, below the 60s file deadline) is
    # partially unanalyzed → propagate incomplete so silently-dropped issues can't inflate (#7).
    timed_out_files = sum(1 for r in results if getattr(r, "incomplete", False))
    if timed_out_files:
        incomplete = True
        logger.warning(
            "%d/%d files had tool subprocess timeouts — marking incomplete (auto-merge blocked)",
            timed_out_files, len(files),
        )
    # 콘텐츠 fetch 가 transient(403 rate-limit/5xx)로 실패한 파일이 있으면 미분석 코드다 —
    # 빈 content 는 이슈0=만점 인플레로 이어지므로 incomplete 로 fail-closed 처리(#6).
    # AutoMergeAction/ApproveAction(#779/#783)이 이 마커로 자동 머지/승인을 차단한다.
    # Files whose content fetch failed transiently are unanalyzed — empty content inflates the
    # score, so mark incomplete (fail-closed, #6) to block auto-merge/approve.
    fetch_failed_count = sum(1 for f in files if getattr(f, "fetch_failed", False))
    if fetch_failed_count:
        incomplete = True
        logger.warning(
            "%d/%d files had transient content-fetch failures — marking incomplete (auto-merge blocked)",
            fetch_failed_count, len(files),
        )
    return results, incomplete


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


def _resolve_review_language(repo_name: str) -> str:
    """AI 리뷰 출력 언어 결정 — Phase 4 PR-12 (사이클 84).

    Resolve AI review output language — Phase 4 PR-12 (Cycle 84).

    우선순위 (priority):
    1. Repository.user_id → User.preferred_language (repo owner 언어)
    2. settings.default_locale (env-based fallback)

    notifier/_language.py 의 3-layer fallback 과 분리 — AI 리뷰는 repo 레벨 (DB 저장 + 다중 채널 재사용).
    notifier 는 channel-level (Telegram/Discord/Slack/Email/GitHub 마다 다른 언어 가능).

    Args:
        repo_name: GitHub full name (owner/repo).

    Returns:
        언어 코드 ('en' / 'ko' / 'ja') — SUPPORTED_LOCALES 영역 내.
    """
    try:
        with SessionLocal() as db:
            repo = db.query(Repository).filter(Repository.full_name == repo_name).first()
            if repo and repo.user_id:
                from src.models.user import User  # noqa: WPS433  # pylint: disable=import-outside-toplevel
                user = db.query(User).filter(User.id == repo.user_id).first()
                if user and user.preferred_language:
                    return user.preferred_language
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.warning(
            "_resolve_review_language failed for repo=%s: %s — falling back to default_locale",
            sanitize_for_log(repo_name), exc,
        )
    return settings.default_locale


def _extract_event_metadata(event: str, data: dict) -> tuple[str, str, str, int | None]:
    """Webhook 페이로드에서 repo_name, commit_sha, commit_message, pr_number를 추출한다."""
    # 브랜치 삭제 push 시 "repository" 키가 None일 수 있으므로 `or {}` 패턴 필수 (PR #124 규칙)
    # "repository" key may be None on branch-delete push — `or {}` pattern required (PR #124 rule)
    repo_name: str = (data.get("repository") or {}).get("full_name", "")
    commit_message = _extract_commit_message(event, data)
    if event == "pull_request":
        # data.get — 같은 블록의 다른 키(repository/head)와 방어 일관성(감사 worker-core-003)
        # data.get for defensive consistency with the other keys in this block.
        pr_number: int | None = data.get("number")
        # head 키도 present-but-None 가능 — 한 단계 더 `or {}` 정규화 (PR #124 패턴)
        # head key may also be present-but-None — normalize one more level (PR #124 pattern)
        commit_sha: str = ((data.get("pull_request") or {}).get("head") or {}).get("sha", "")
    else:
        pr_number = None
        # 브랜치 삭제 시 "after"가 없거나 0000...000일 수 있음 — .get() 방어
        # Branch-delete sends "after" as missing or all-zeros — use .get() defensively
        commit_sha = data.get("after", "")
    return repo_name, commit_sha, commit_message, pr_number


def _is_blank_sha(sha: str) -> bool:
    """SHA 가 비었거나 all-zeros 인지 판정 (브랜치/태그 삭제 push 의 GitHub zero-SHA).
    True if the SHA is empty or all-zeros (GitHub's zero-SHA for branch/tag-delete pushes).

    GitHub 는 브랜치/태그 삭제 시 after 를 40-zero SHA 로 보낸다 (예: src/github_client/repos.py
    의 REMOTE_SHA 비교와 동일 컨벤션). 길이에 무관하게 all-zeros 를 포착하도록 set 비교 사용.
    GitHub sends a 40-zero after-SHA on branch/tag deletion (same convention as the REMOTE_SHA
    check in src/github_client/repos.py). Uses a set comparison to catch all-zeros of any length.
    """
    return not sha or set(sha) == {"0"}


def _ensure_repo(db: Session, repo_name: str, commit_sha: str) -> tuple[Repository, str] | None:
    """리포를 조회·등록하고 owner token을 결정한다. SHA 중복이면 None을 반환한다."""
    owner_token: str = settings.github_token
    repo = repository_repo.find_by_full_name(db, repo_name)
    if not repo:
        try:
            repo = repository_repo.save_new(
                db, Repository(full_name=repo_name, telegram_chat_id=settings.telegram_chat_id)
            )
            db.commit()
        except IntegrityError:
            # 동시 webhook race — 다른 워커가 같은 repo 를 먼저 INSERT (full_name unique 위반).
            # rollback 후 재조회로 복구해 uncaught IntegrityError 의 워커 abort 를 방지한다.
            # Concurrent webhook race — another worker INSERTed the same repo first (full_name unique).
            # Recover via rollback + re-fetch to prevent an uncaught IntegrityError from aborting the worker.
            db.rollback()
            repo = repository_repo.find_by_full_name(db, repo_name)
            if repo is None:
                # 재조회도 None = unique-race 가 아닌 진짜 오류 → 전파 (복구로 삼키지 않음)
                # Re-fetch is None too = a genuine error, not the unique-race → propagate (don't swallow)
                raise
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
    if existing.pr_number is not None:
        # 동일 SHA가 이미 다른 PR#로 gate된 경우 덮어쓰지 않는다 (first-writer-wins) —
        # _race_recover_existing 과 대칭. 동일 head SHA 멀티 PR 시 잘못된 PR 에 gate 적용 차단.
        # Don't overwrite when this SHA was already gated for a different PR (first-writer-wins),
        # mirroring _race_recover_existing — prevents gate actions hitting the wrong PR.
        logger.warning(
            "_regate_pr_if_needed: sha=%s already gated for PR #%d, skip PR #%d (first-writer-wins)",
            commit_sha[:8], existing.pr_number, pr_number,
        )
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
    if existing.result is None:
        # result=None 이면 run_gate_check 내부에서 AttributeError 발생 — 조기 종료
        # Skip if result is None to avoid AttributeError inside run_gate_check
        logger.warning("_regate_pr_if_needed: analysis %d has no result, skipping gate", existing.id)
        return
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
        # 사고에서 line 211 의 `logger.error(... %s, exc)` 가 메시지만 남겨
        # Railway 로그에서 원인 추적 불가능했던 문제 해결.
        # Phase 2: use logger.exception so the full traceback is captured in
        # Railway logs (the previous `logger.error` only left the exc message,
        # making the PR #105 silent-skip incident unreproducible from logs).
        logger.exception(
            "Re-gate check failed (pr=#%d, sha=%s)", pr_number, commit_sha[:8],
        )


async def _race_recover_existing(
    db: Session,
    params: _AnalysisSaveParams,
    existing,
):
    """기존 Analysis 발견 시 race-recovery 분기 — 사이클 93 PR-B (S3776 분리).

    Race-recovery branch when existing Analysis is found (Cycle 93 PR-B — S3776 split).
    PR 이벤트가 push 이벤트와 동시 도착해 dedup 통과 시 pr_number 보정 + gate 재실행.
    """
    try:
        repo_config = get_repo_config(db, params.repo_name)
    except (SQLAlchemyError, KeyError):
        repo_config = None

    if params.pr_number is None or existing.pr_number is not None:
        return repo_config
    if existing.result is None:
        # result=None 이면 run_gate_check 내부에서 AttributeError 발생 — 조기 종료
        # Skip if result is None to avoid AttributeError inside run_gate_check
        logger.warning("_race_recover_existing: analysis %d has no result, skipping gate", existing.id)
        return repo_config

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
        # logger.exception 으로 stack trace 보존 — Railway 로그에서 진짜 원인 추적
        # logger.exception preserves the stack trace for Railway log triage
        logger.exception(
            "Race-recovery gate check failed (pr=#%d, sha=%s)",
            params.pr_number, params.commit_sha[:8],
        )
    return repo_config


async def _save_and_gate(db: Session, params: _AnalysisSaveParams):
    """Analysis를 DB에 저장하고 Gate Engine을 실행한다.

    Returns:
        (repo_config, analysis_id, result_dict) 튜플.
        중복 커밋이면 (repo_config_or_None, None, None).
    사이클 93 PR-B: race-recovery 분기 = `_race_recover_existing` 분리 (S3776 20→<15).
    """
    repo = repository_repo.find_by_full_name(db, params.repo_name)
    if repo is None:
        logger.warning(
            "Repository not found in second session: %s",
            sanitize_for_log(params.repo_name),
        )
        return None, None, None
    # 멱등성 재확인 — 동시 Webhook 전달로 인한 중복 Analysis 삽입 방지 (TOCTOU 완화)
    # Idempotency re-check — defends against concurrent webhooks racing past the first dedup.
    existing = analysis_repo.find_by_sha(db, params.commit_sha, repo.id)
    if existing is not None:
        logger.info("Commit %s already saved (concurrent insert detected), skipping", params.commit_sha)
        repo_config = await _race_recover_existing(db, params, existing)
        return repo_config, None, None
    result_dict = build_analysis_result_dict(
        params.ai_review, params.score_result, params.analysis_results,
        source="pr" if params.pr_number else "push",
    )
    # 정적분석 불완전(타임아웃) 시 마커 — run_gate_check 가 읽어 auto-merge 차단 + DB 관측 보존
    # Mark incomplete static analysis (timeout) — run_gate_check reads it to block
    # auto-merge; also persisted on the Analysis row for observability.
    if params.static_incomplete:
        result_dict["static_analysis_incomplete"] = True
    ai = params.ai_review
    # AI genuine 실패(#25/#814) 시에만 score/grade NULL 저장 → 집계 오염 차단(쿼리 변경 0).
    # 입력-diff 절단은 NULL 제외(점수 유지)·예외(no_api_key/empty_diff)는 _persisted_score_is_unreliable 도크스트링 참조.
    # NULL-persist score/grade only on a genuine AI failure — see helper docstring (truncation excluded).
    _score_unreliable = _persisted_score_is_unreliable(result_dict)
    analysis, created = analysis_repo.save_new(db, Analysis(
        repo_id=repo.id,
        commit_sha=params.commit_sha,
        commit_message=params.commit_message,
        pr_number=params.pr_number,
        score=None if _score_unreliable else params.score_result.total,
        grade=None if _score_unreliable else params.score_result.grade,
        result=result_dict,
        author_login=params.author_login,
        review_model=getattr(ai, "used_model", None),
        input_tokens=getattr(ai, "input_tokens", None) or None,
        output_tokens=getattr(ai, "output_tokens", None) or None,
    ))
    if not created:
        # 동시 insert 가 find_by_sha 재확인(410)을 통과했으나 DB unique 제약이 차단 →
        # 기존 레코드 반환. find_by_sha race 경로와 동일 처리: 중복 알림/PR 코멘트 방지
        # (result_dict=None race-recovery 신호 재사용).
        # Concurrent insert raced past the find_by_sha re-check but was blocked by the DB
        # constraint → existing returned. Same handling as the find_by_sha race path:
        # prevent duplicate notify/PR-comment via the result_dict=None race-recovery signal.
        logger.info(
            "Concurrent insert blocked by DB constraint (sha=%s) — race-recovery, skipping duplicate gate/notify",
            params.commit_sha,
        )
        repo_config = await _race_recover_existing(db, params, analysis)
        return repo_config, None, None
    analysis_id = analysis.id
    try:
        repo_config = get_repo_config(db, params.repo_name)
    except (SQLAlchemyError, KeyError):
        logger.warning(
            "Failed to load repo config for %s, using defaults",
            sanitize_for_log(params.repo_name),
        )
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
        if isinstance(exc, BaseException):
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
            pr_head_ref = _extract_pr_head_ref(event, data)

            # 브랜치/태그 삭제 push 는 zero-SHA(all-zeros) 또는 빈 SHA — 분석할 커밋이 없다.
            # 가드 없이 진입하면 _collect_files 가 존재하지 않는 SHA 를 GitHub 에 조회 → 매번 404 + 예외 로그.
            # Branch/tag-delete push carries a zero-SHA (all-zeros) or empty SHA — no commit to analyze.
            # Without this guard, _collect_files queries a nonexistent SHA on GitHub → a 404 + exception log every time.
            if _is_blank_sha(commit_sha):
                logger.info(
                    "Skipping %s — no analyzable commit SHA (branch/tag delete or missing head)",
                    repo_log,
                )
                return

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
            # Phase 4 PR-12 (사이클 84) — repo owner 언어 결정 (User.preferred_language → default_locale)
            # AI 리뷰 출력 언어 = repo owner 의 preferred_language. RepoConfig.notification_language 는
            # 알림 채널 영역 (notifier/_language.py) — AI 리뷰는 DB 저장 + 다중 채널 재사용 → repo 레벨 결정.
            # Phase 4 PR-12 (Cycle 84) — resolve repo owner's language (User.preferred_language → default_locale).
            # AI review output language = repo owner's preferred_language. RepoConfig.notification_language
            # is for channel-level (notifier/_language.py) — AI review is DB-stored + reused across channels.
            review_language = _resolve_review_language(repo_name)
            # 리포 설정 단일 조회 — review_model + disabled_tools 양쪽에 사용
            # Single DB fetch — used for both review_model and disabled_tools
            repo_review_model: str | None = None
            _static_repo_cfg: object | None = None
            # 리포별 AI 리뷰 on/off — 조회 실패/부재 시 default True(기존 동작 보존)
            # Per-repo AI review on/off — default True on fetch failure/absence
            _ai_review_enabled = True
            try:
                with SessionLocal() as db_cfg:
                    _cfg = get_repo_config(db_cfg, repo_name)
                    repo_review_model = _cfg.review_model or None
                    _static_repo_cfg = _cfg
                    _ai_review_enabled = getattr(_cfg, "ai_review_enabled", True)
            except Exception:  # noqa: BLE001  # pylint: disable=broad-exception-caught
                logger.debug(
                    "repo_config fetch failed for %s — using defaults for model and disabled_tools",
                    repo_name,
                )

            with stage_timer("analyze", repo=repo_log) as ctx:
                static_outcome, ai_review = await asyncio.gather(
                    _run_static_with_timeout(files, repo_config=_static_repo_cfg),
                    review_code(
                        settings.anthropic_api_key, commit_message, patches,
                        language=review_language,
                        model=repo_review_model,
                        enabled=_ai_review_enabled,
                    ),
                )
                # (결과 리스트, 타임아웃 여부) — 타임아웃 시 auto-merge 차단 신호로 전파
                # (results, timed_out) — timed_out propagates as the auto-merge block signal
                analysis_results, static_timed_out = static_outcome
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
                    static_incomplete=static_timed_out,
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
