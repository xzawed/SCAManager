"""Gate Engine — 3개 독립 옵션: Review Comment / Approve / Auto Merge.

Sprint E: 3개 옵션은 Action 클래스 + GATE_ACTIONS Registry 패턴으로 전환됨.
Sprint E: The 3 options have been migrated to Action classes via GATE_ACTIONS registry.
"""
import asyncio
import logging
from datetime import datetime, timezone
from html import escape

import httpx
from sqlalchemy.orm import Session
from src.config import settings
from src.database import WorkerSessionLocal as SessionLocal  # 독립 세션 열기용 — asyncio.gather 공유 세션 오염 방지
# SessionLocal imported at module level for independent sessions in asyncio.gather coroutines.
from src.config_manager.manager import get_repo_config, RepoConfigData
# Action Registry — 3개 옵션을 GATE_ACTIONS 리스트로 관리. import 시 자동 등록.
# Action Registry — manages 3 gate options via GATE_ACTIONS list. Registered at import time.
from src.gate.actions import GATE_ACTIONS, GateContext
import src.gate.actions.review_comment  # noqa: F401 — registers ReviewCommentAction  # pylint: disable=cyclic-import,unused-import
import src.gate.actions.approve  # noqa: F401 — registers ApproveAction  # pylint: disable=cyclic-import,unused-import
import src.gate.actions.auto_merge  # noqa: F401 — registers AutoMergeAction  # pylint: disable=cyclic-import,unused-import
from src.gate.github_review import (
    get_pr_mergeable_state, get_pr_base_ref,
)
from src.gate import _merge_attempt_states as _states
from src.gate.merge_failure_advisor import get_advice
from src.gate.merge_reasons import is_retriable_tag, DEFERRED
from src.gate.native_automerge import (
    PATH_NATIVE_ENABLE,
    enable_or_fallback_with_path as native_enable_with_path,
)
from src.gate.retry_policy import parse_reason_tag, should_retry
from src.github_client.checks import get_ci_status, get_required_check_contexts
from src.i18n.loader import get_text
from src.notifier.merge_failure_issue import create_merge_failure_issue
from src.notifier.telegram import telegram_post_message
from src.repositories import merge_retry_repo
from src.shared.log_safety import sanitize_for_log
from src.shared.merge_metrics import log_merge_attempt

logger = logging.getLogger(__name__)


async def run_gate_check(  # pylint: disable=too-many-positional-arguments
    repo_name: str,
    pr_number: int | None,
    analysis_id: int,
    result: dict,
    github_token: str,
    db: Session,
    config: RepoConfigData | None = None,
    commit_sha: str | None = None,
) -> None:
    """PR 이벤트 시 3개 독립 옵션을 각각 실행한다.

    1. Review Comment — pr_review_comment=True 이면 PR에 상세 AI 리뷰 댓글 발송
    2. Approve       — approve_mode에 따라 GitHub APPROVE/REQUEST_CHANGES 또는 Telegram 요청
    3. Auto Merge    — auto_merge=True이고 score >= merge_threshold이면 squash merge

    세 옵션은 완전 독립 — 어떤 조합이든 가능하다.
    pr_number=None(push 이벤트)이면 모든 PR 관련 액션을 건너뛴다.
    config: 이미 로드된 RepoConfigData — None이면 DB에서 직접 조회한다.
    commit_sha: 실제 분석된 커밋 SHA — auto-merge 의 SHA 결속 가드용(미전달 시 가드 미적용).
    commit_sha: the analyzed commit SHA — used by the auto-merge binding guard (omitted → no guard).
    """
    if pr_number is None:
        return

    if config is None:
        config = get_repo_config(db, repo_name)
    score = result.get("score", 0)

    # Sprint E: GATE_ACTIONS Registry로 3 옵션 병렬 실행.
    # 각 Action은 내부에서 독립 SessionLocal()을 열어 P0-H 규약 준수.
    # Sprint E: Dispatch 3 options via GATE_ACTIONS registry in parallel.
    # Each Action opens its own SessionLocal() to comply with the P0-H invariant.
    ctx = GateContext(
        repo_name=repo_name, pr_number=pr_number, analysis_id=analysis_id,
        result=result, github_token=github_token, config=config, score=score,
        commit_sha=commit_sha,
    )
    applicable = [a for a in GATE_ACTIONS if a.is_applicable(config)]
    outcomes = await asyncio.gather(
        *[a.execute(ctx) for a in applicable],
        return_exceptions=True,
    )
    # 옵션별 예상 외 예외 로깅 — 옵션 내부 try/except 가 못 잡은 케이스만
    # Log unexpected exceptions per option — only those not caught internally.
    for action, outcome in zip(applicable, outcomes):
        if isinstance(outcome, BaseException):
            logger.error(
                "Gate action [%s] unexpected exception: %s",
                type(action).__name__, type(outcome).__name__,
                exc_info=(type(outcome), outcome, outcome.__traceback__),
            )


async def _run_auto_merge(  # pylint: disable=too-many-arguments,too-many-locals
    config: RepoConfigData,
    github_token: str,
    repo_name: str,
    pr_number: int,
    score: int,
    *,
    analysis_id: int | None = None,
    result: dict | None = None,
    analyzed_sha: str | None = None,
) -> None:
    """Auto Merge 옵션 — AutoMergeAction(자동)·handle_gate_callback(반자동)이 위임받는 실제 구현.
    Actual implementation delegated to by AutoMergeAction (auto) and handle_gate_callback (semi-auto).
    P0-H: 독립 SessionLocal() 사용.

    result: 2nd-LLM 검증 가드용 분석 결과 dict(미전달 시 빈 dict — 가드는 키 미설정/밴드 밖이면 skip).
    result: analysis result dict for the 2nd-LLM verifier guard (defaults to empty; the guard skips
    when no key / outside band).

    analyzed_sha: `score` 를 산출한 실제 분석 대상 커밋 SHA — 머지를 이 SHA 에 결속한다.
    미전달(None) 시 결속 가드 미적용(하위 호환).
    analyzed_sha: the commit SHA that actually produced `score` — binds the merge to it.
    None (omitted) disables the binding guard (backward compatible).
    """
    if not (config.auto_merge and score >= config.merge_threshold):
        return
    # 2nd-LLM 검증 가드 (단일 출처) — 자동/반자동 양 경로 공유(#859 P1-1 parity).
    # DB 세션 열기 전 수행 — OpenAI 호출(타임아웃) 동안 세션 점유 방지. 차단 시 머지 미진행.
    # 2nd-LLM verifier guard (single source) — shared by auto/semi-auto paths (#859 P1-1 parity).
    # Run before opening the DB session so the OpenAI call doesn't hold one. Block → no merge.
    # 🔴 민감 경로 가드 (B6-a) — 인증·마이그레이션·CI 워크플로 변경은 사람 검토 전까지 보류.
    #   점수 게이트는 **경로 민감도를 모른다**: 60점만 넘으면 auth 변경도 무검토 머지된다
    #   (실측 #1102~#1107 6건 전부 reviews=0 · 그중 #1104 는 토큰 유출 P0 보안 변경).
    #   검증자 가드와 같은 자리에 둬 자동·반자동 양 경로가 공유한다.
    # Score says nothing about path sensitivity; hold auth/migration/CI-workflow changes for review.
    from src.gate.sensitive_paths import sensitive_paths_block_merge  # pylint: disable=import-outside-toplevel
    if await sensitive_paths_block_merge(
        github_token=github_token, repo_name=repo_name, pr_number=pr_number,
    ):
        return
    from src.gate.merge_verifier import verifier_blocks_merge  # pylint: disable=import-outside-toplevel
    if await verifier_blocks_merge(
        github_token=github_token, repo_name=repo_name, pr_number=pr_number,
        result=result or {}, score=score, merge_threshold=config.merge_threshold,
    ):
        return
    with SessionLocal() as db:
        if not settings.merge_retry_enabled:
            await _run_auto_merge_legacy(
                config, github_token, repo_name, pr_number, score,
                analysis_id=analysis_id, db=db, analyzed_sha=analyzed_sha,
            )
            return
        try:
            await _run_auto_merge_retry(
                config, github_token, repo_name, pr_number, score,
                analysis_id=analysis_id, db=db, analyzed_sha=analyzed_sha,
            )
        except (httpx.HTTPError, KeyError, RuntimeError, ValueError) as exc:
            logger.error(
                "Auto Merge 실패 (repo=%s, pr=%d): %s",
                repo_name, pr_number, type(exc).__name__,
            )


async def _run_auto_merge_retry(  # pylint: disable=too-many-arguments,too-many-locals
    config: RepoConfigData,
    github_token: str,
    repo_name: str,
    pr_number: int,
    score: int,
    *,
    analysis_id: int | None = None,
    db: Session | None = None,
    analyzed_sha: str | None = None,
) -> None:
    """Phase 12 재시도 경로의 핵심 로직 — _run_auto_merge 에서 위임받음.
    Core logic of the Phase 12 retry path — delegated from _run_auto_merge.

    1. PR mergeable_state + head_sha 조회
    1-1. 🔴 SHA 결속 가드 — head 가 분석된 SHA 와 다르면 머지 금지
    2. merge_pr 즉시 시도 (SHA 원자성 가드 포함)
    3. 성공 → 기록 후 반환
    4. 실패 태그 분류 → 터미널이면 _handle_terminal_merge_failure
    5. CI 상태 판별 → 재시도 불가면 터미널 처리
    6. 재시도 가능 → 큐 등록 + 최초 지연 알림
    """
    # 1. PR 상태 + head_sha 조회
    # 1. Get PR state + head_sha
    try:
        _state, head_sha = await get_pr_mergeable_state(github_token, repo_name, pr_number)
    except httpx.HTTPError as exc:
        logger.warning("get_pr_mergeable_state 실패 (pr=%d): %s", pr_number, exc)
        head_sha = ""

    # 1-1. 🔴 SHA 결속 가드 (fail-closed) — score 를 산출한 커밋과 현재 head 가 다르면 머지 금지.
    # 분석(정적 60s + AI 리뷰)이 도는 동안 push/force-push 로 head 가 B 로 바뀌면, 이 가드가
    # 없을 때 B 가 A 의 점수로 머지된다(미검증 코드 자동 머지). 여기서 드롭해도 손실 없음 —
    # B 의 synchronize 웹훅이 B 를 분석해 자체 게이트를 돌린다. 큐 등록도 하지 않는다:
    # 잘못된 SHA 가 큐에 들어가면 나중에 재시도가 A 의 점수로 B 를 머지해버린다.
    # 1-1. SHA binding guard (fail-closed) — refuse to merge when the live head is not the commit
    # that produced `score`. During analysis (60s static + AI review) a push can move the head to B;
    # without this guard B gets merged under A's score. Dropping here loses nothing — B's own
    # synchronize webhook analyses and gates B. We also skip the retry queue on purpose: a row
    # keyed by the wrong SHA would let a later retry merge B under A's score.
    if analyzed_sha and head_sha and head_sha != analyzed_sha:
        logger.warning(
            "analysis SHA drift — auto-merge 차단 (repo=%s, pr=%d, analyzed=%s, head=%s)",
            sanitize_for_log(repo_name), pr_number, analyzed_sha[:8], head_sha[:8],
        )
        return

    # 2. Native auto-merge enable 시도 — 실패 시 REST merge_pr 폴백 (Tier 3 PR-A)
    # Phase 3 PR-B1: enable_or_fallback_with_path 사용 — outcome.path 로 state 라벨링
    # Phase 3 PR-B1: use enable_or_fallback_with_path so outcome.path drives state
    #
    # 머지 대상을 분석된 SHA 로 결속 — head 조회가 실패해도(head_sha="") GitHub 이 sha 파라미터로
    # 원자성을 검증하므로 head 가 움직였으면 409 로 거절된다(#962 SHA 원자성 계약과 동일 지점).
    # Bind the merge to the analyzed SHA — even when the head lookup failed (head_sha=""), GitHub
    # validates the `sha` parameter and rejects with 409 if the head moved (#962 SHA atomicity).
    merge_sha = analyzed_sha or head_sha
    outcome = await native_enable_with_path(
        github_token, repo_name, pr_number, expected_sha=merge_sha or None
    )
    ok, reason, observed_sha = outcome.ok, outcome.reason, outcome.head_sha

    # 🔴 재시도 큐 결속은 **분석된 SHA(A)** 우선 — observed_sha 아님 (종합감사 P1-1, Grok REAL).
    # 1-1 가드 통과 후 force-push 로 head 가 B 로 드리프트하면 merge_pr 내부 조회가 observed_sha=B
    # 를 관측할 수 있다. 큐를 B 로 결속하면 재시도 워커의 `head != row.commit_sha` 검사가
    # head==B==B 로 드리프트를 놓쳐 미검증 B 를 A 의 점수로 머지한다. analyzed_sha 로 결속하면
    # 이후 head 가 B 로 움직여도 워커가 `B != A` 로 drift 를 잡아 abandon → fail-closed 유지.
    # analyzed_sha 미상일 때만 observed_sha/merge_sha 로 폴백(기존 동작 보존).
    # Bind the retry queue to the ANALYZED sha (A), not the observed one: a force-push after the
    # 1-1 guard can make merge_pr observe head=B; binding to B would let the worker's drift check
    # (head != row.commit_sha) miss it and merge unverified B under A's score. Binding to A means
    # a later drift to B is caught by the worker (B != A → abandon). Fall back only when A unknown.
    effective_sha = analyzed_sha or observed_sha or merge_sha

    # 3. 성공 — 기록 후 반환 (Phase 3 PR-B1: path 기반 state 라벨링)
    # 3. Success — log and return (Phase 3 PR-B1: state derived from path)
    if ok:
        # native enable 성공 → enabled_pending_merge (GitHub 비동기 머지 대기)
        # REST 폴백 즉시 성공 → direct_merged (이미 머지됨)
        # native enable success → enabled_pending_merge (awaiting GitHub async merge)
        # REST fallback immediate success → direct_merged (already merged)
        if outcome.path == PATH_NATIVE_ENABLE:
            new_state = _states.ENABLED_PENDING_MERGE
            enabled_at = datetime.now(timezone.utc)
        else:
            new_state = _states.DIRECT_MERGED
            enabled_at = None

        if analysis_id is not None and db is not None:
            try:
                log_merge_attempt(
                    db, analysis_id=analysis_id, repo_name=repo_name,
                    pr_number=pr_number, score=score,
                    threshold=config.merge_threshold, success=True, reason=None,
                    state=new_state, enabled_at=enabled_at,
                )
            except Exception as log_exc:  # pylint: disable=broad-except
                logger.warning("merge_attempt 기록 실패: %s", log_exc)
        logger.info(
            "PR #%d auto-merged (state=%s): %s", pr_number, new_state, repo_name,
        )
        return

    # 4. 실패 분류 — 터미널이면 즉시 처리
    # 4. Classify failure — handle terminal immediately
    reason_tag = parse_reason_tag(reason)
    # 재시도 가능 태그 판별을 merge_reasons.is_retriable_tag 단일 출처로 위임.
    # (기존: (UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT) 튜플 하드코딩 — _RETRIABLE_TAGS 와 drift 위험)
    # Delegate retriable-tag check to the single source merge_reasons.is_retriable_tag.
    # (was: hardcoded (UNSTABLE_CI, UNKNOWN_STATE_TIMEOUT) tuple — could drift from _RETRIABLE_TAGS)
    if not is_retriable_tag(reason_tag):
        await _handle_terminal_merge_failure(
            config=config, github_token=github_token, repo_name=repo_name,
            pr_number=pr_number, score=score, reason=reason, reason_tag=reason_tag,
            analysis_id=analysis_id, db=db,
        )
        return

    # 5. CI 상태 추가 판별 (D2) — F1: PR base 브랜치 동적 사용
    # 5. Disambiguate CI state (D2) — F1: use actual PR base ref
    base_ref = await get_pr_base_ref(github_token, repo_name, pr_number)
    ci_status = await _get_ci_status_safe(
        github_token, repo_name, effective_sha, base_ref=base_ref,
    )

    if not should_retry(reason_tag, ci_status):
        # CI 실제 실패 또는 판별 후 터미널 상태
        # CI actually failed or state is terminal after disambiguation
        await _handle_terminal_merge_failure(
            config=config, github_token=github_token, repo_name=repo_name,
            pr_number=pr_number, score=score, reason=reason, reason_tag=reason_tag,
            analysis_id=analysis_id, db=db,
        )
        return

    # 6. 재시도 큐 등록 (D4, D5, D6)
    # 6. Enqueue for retry (D4, D5, D6)
    await _enqueue_merge_retry(
        config=config, repo_name=repo_name, pr_number=pr_number, score=score,
        effective_sha=effective_sha, reason_tag=reason_tag, ci_status=ci_status,
        analysis_id=analysis_id, db=db,
    )


async def _get_ci_status_safe(
    github_token: str,
    repo_name: str,
    commit_sha: str,
    *,
    base_ref: str = "main",
) -> str:
    """CI 상태를 안전하게 조회한다 — 오류 시 'unknown' 반환.
    Safely fetch CI status — returns 'unknown' on error.

    F1: base_ref 파라미터로 PR 의 실제 base 브랜치 BPR 조회 — develop/staging 등
    main 이 아닌 base 에서도 정확. 호출자가 모르면 "main" 기본값 사용.

    🔴 **PARITY GUARD**: 본 함수는 `src/services/merge_retry_service.py::
    _get_ci_status_safe` 와 의도적 동일 구현 (단일/워커 경로 일관성). 한쪽만
    수정하면 두 경로의 CI 상태 판정이 발산해 운영 사고. 변경 시 양쪽 동시
    수정 필수 + `tests/unit/test_ci_status_safe_parity.py` 회귀 가드 통과 확인.

    **PR-5A-2 마이그레이션 가이드** (실제 dedup 진행 시):
      1. `src/shared/ci_utils.py` 신규 — `get_ci_status_safe()` 단일 출처
      2. 본 함수와 worker 측 함수를 shared 모듈 호출 wrapper 로 변경
      3. **테스트 patch 경로 마이그레이션 필수**:
         - `src.gate.engine.get_required_check_contexts` → `src.shared.ci_utils.get_required_check_contexts`
         - `src.gate.engine.get_ci_status` → `src.shared.ci_utils.get_ci_status`
         - `src.services.merge_retry_service.get_required_check_contexts` → 동일
         - `src.services.merge_retry_service.get_ci_status` → 동일
      4. `tests/unit/gate/test_engine.py` + `test_auto_merge_enqueue.py` +
         `tests/integration/test_retry_*.py` 의 patch 대상 일괄 grep+replace
      5. parity 회귀 가드는 단일 함수 검증으로 단순화 (8 tests → 4 tests 추정)

    INTENTIONAL DUPLICATE — keep both copies in sync; parity test enforces.
    """
    try:
        required = await get_required_check_contexts(github_token, repo_name, base_ref)
    except httpx.HTTPError:
        required = None  # None 이면 모든 체크 고려 / None means "consider all checks"

    # 방어층: BPR Required 미설정으로 빈 set 이 반환되면 None 으로 통일
    # checks.py 의 fallback 과 이중 안전 — 호출 측에서도 명시적으로 처리
    # Defense layer: unify empty set (no BPR required checks) to None
    # — double safety with checks.py fallback, explicit handling at call site
    if not required:
        required = None

    try:
        return await get_ci_status(
            github_token, repo_name, commit_sha,
            required_contexts=required,
        )
    except httpx.HTTPError:
        return "unknown"


async def _enqueue_merge_retry(  # pylint: disable=too-many-arguments
    *,
    config: RepoConfigData,
    repo_name: str,
    pr_number: int,
    score: int,
    effective_sha: str,
    reason_tag: str,
    ci_status: str,
    analysis_id: int | None,
    db: Session | None,
) -> None:
    """재시도 큐에 등록하고 최초 지연 시 Telegram 알림을 전송한다.
    Enqueue for merge retry and send Telegram notification on first deferral.
    """
    if analysis_id is None or db is None:
        # F3: warning 격상 — 큐잉 미수행은 정상 동작이 아닌 호출 누락 신호
        # F3: elevated to warning — missing queue is not normal, indicates caller omission
        logger.warning(
            "PR #%d auto-merge 큐잉 생략 (analysis_id=%s, db=%s) — "
            "레거시 호출 또는 인자 누락. 재시도 추적 불가.",
            pr_number,
            "set" if analysis_id is not None else "None",
            "set" if db is not None else "None",
        )
        return

    try:
        log_merge_attempt(
            db, analysis_id=analysis_id, repo_name=repo_name,
            pr_number=pr_number, score=score,
            threshold=config.merge_threshold, success=False,
            reason=f"{reason_tag}:{DEFERRED}",
        )
    except Exception as log_exc:  # pylint: disable=broad-except
        logger.warning("merge_attempt 기록 실패 (deferred): %s", log_exc)

    try:
        enqueued = merge_retry_repo.enqueue_or_bump(
            db,
            repo_full_name=repo_name,
            pr_number=pr_number,
            analysis_id=analysis_id,
            commit_sha=effective_sha or "",
            score=score,
            threshold_at_enqueue=config.merge_threshold,
            notify_chat_id=config.notify_chat_id,
            max_attempts=settings.merge_retry_max_attempts,
            initial_next_retry_seconds=settings.merge_retry_initial_backoff_seconds,
        )
        if enqueued.is_first_deferral:
            # 3-layer 사용자 언어 결정 (User → RepoConfig → settings.default_locale)
            # 사이클 152 Sprint 2 — deferred 알림도 동기 경로 i18n 적용.
            # 3-layer language resolve; Cycle 152 Sprint 2 — localize deferred notice.
            from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
            with SessionLocal() as db_lang:
                language = resolve_notification_language(db_lang, config=config)
            await _notify_merge_deferred(
                repo_name=repo_name,
                pr_number=pr_number,
                score=score,
                threshold=config.merge_threshold,
                reason_tag=reason_tag,
                ci_status=ci_status,
                chat_id=config.notify_chat_id or settings.telegram_chat_id,
                language=language,
            )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "merge_retry_repo.enqueue_or_bump 실패 (pr=%d): %s", pr_number, exc
        )


def _resolve_legacy_merge_state(ok: bool, outcome) -> tuple[str, "datetime | None"]:
    """legacy auto-merge state 분류 — 사이클 93 PR-B (S3776 분리).

    Resolve legacy merge state (Cycle 93 PR-B — extracted to reduce S3776).
    - native enable 성공 → ENABLED_PENDING_MERGE (enabled_at = now)
    - REST 폴백 성공 → DIRECT_MERGED (enabled_at = None)
    - 실패 → LEGACY (enabled_at = None — state 분류 의미 없음)
    """
    if ok and outcome.path == PATH_NATIVE_ENABLE:
        return _states.ENABLED_PENDING_MERGE, datetime.now(timezone.utc)
    if ok:
        return _states.DIRECT_MERGED, None
    return _states.LEGACY, None


async def _run_auto_merge_legacy(  # pylint: disable=too-many-arguments,too-many-locals
    config: RepoConfigData,
    github_token: str,
    repo_name: str,
    pr_number: int,
    score: int,
    *,
    analysis_id: int | None = None,
    db: Session | None = None,
    analyzed_sha: str | None = None,
) -> None:
    """Auto Merge 레거시 경로 — 재시도 없이 단일 시도.

    merge_retry_enabled=False 일 때 _run_auto_merge 가 이 함수로 위임한다.
    Legacy Auto Merge path — single attempt without retry.
    _run_auto_merge delegates here when merge_retry_enabled=False.

    analyzed_sha: 분석된 커밋 SHA — expected_sha 로 전달해 GitHub 이 원자성을 검증하게 한다.
    analyzed_sha: the analyzed commit SHA — passed as expected_sha so GitHub enforces atomicity.
    """
    try:
        # Tier 3 PR-A: native auto-merge 우선 시도, 실패 시 REST merge_pr 폴백
        # Phase 3 PR-B1: with_path 버전 사용 → outcome.path 로 state 라벨링
        # Tier 3 PR-A: try native auto-merge first, fall back to REST merge_pr.
        # Phase 3 PR-B1: use with_path so state can be derived from outcome.path.
        #
        # 🔴 expected_sha=analyzed_sha 필수 — 미전달 시 native 가 스스로 live head 를 조회해
        # 그 SHA 로 머지하므로, 분석 중 push 된 미검증 커밋이 이전 점수로 머지된다(재시도 경로와 동일 결함).
        # 🔴 expected_sha=analyzed_sha is required — without it native fetches the live head itself
        # and merges that, so a commit pushed mid-analysis merges under the old score (same defect
        # as the retry path had).
        outcome = await native_enable_with_path(
            github_token, repo_name, pr_number, expected_sha=analyzed_sha or None,
        )
        ok, reason = outcome.ok, outcome.reason

        # Phase 3 PR-B1: state 분류 분리 (사이클 93 PR-B — S3776 16→<15)
        # state derivation extracted to helper (Cycle 93 PR-B — S3776 16→<15)
        new_state, enabled_at = _resolve_legacy_merge_state(ok, outcome)

        # Phase F.1: 모든 시도 DB 기록 — 관측 실패가 파이프라인을 중단시키지 않도록
        # Phase F.1: Record every attempt in DB — observability failures must not interrupt the pipeline.
        # log_merge_attempt 자체 오류는 독립 try/except 로 격리.
        # Errors from log_merge_attempt are isolated in their own try/except block.
        if analysis_id is not None and db is not None:
            try:
                log_merge_attempt(
                    db,
                    analysis_id=analysis_id,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    score=score,
                    threshold=config.merge_threshold,
                    success=ok,
                    reason=reason,
                    state=new_state,
                    enabled_at=enabled_at,
                )
            except Exception as log_exc:  # pylint: disable=broad-except
                logger.warning(
                    "merge_attempt 기록 실패 (repo=%s, pr=%d): %s",
                    repo_name, pr_number, log_exc,
                )

        if ok:
            logger.info("PR #%d auto-merged: %s", pr_number, sanitize_for_log(repo_name))
            return

        # Phase 3 PR-11 — 3-layer 사용자 언어 결정 (User → RepoConfig → settings.default_locale)
        # 사이클 149 Sprint 3 — get_advice 도 동일 언어 적용 (조언 텍스트 i18n)
        # Phase 3 PR-11 — 3-layer language resolve; Cycle 149 Sprint 3 — advice text also localized
        from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
        with SessionLocal() as db_lang:
            language = resolve_notification_language(db_lang, config=config)
        advice = get_advice(reason, language)

        logger.warning(
            "PR #%d auto-merge 실패 (repo=%s): %s", pr_number, repo_name, reason
        )
        await _notify_merge_failure(
            repo_name=repo_name,
            pr_number=pr_number,
            score=score,
            threshold=config.merge_threshold,
            reason=reason or "unknown",
            advice=advice,
            chat_id=config.notify_chat_id or settings.telegram_chat_id,
            language=language,
        )
        if config.auto_merge_issue_on_failure:
            try:
                await create_merge_failure_issue(
                    github_token=github_token,
                    repo_name=repo_name,
                    pr_number=pr_number,
                    score=score,
                    threshold=config.merge_threshold,
                    reason=reason or "unknown",
                    advice=advice,
                    language=language,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning(
                    "create_merge_failure_issue 실패 (pr=%d): %s", pr_number, exc
                )
    # Phase F QW4: RuntimeError/ValueError 도 포착해 알림 스킵 방지
    # Phase F QW4: also catch RuntimeError/ValueError to prevent notification skip.
    except (httpx.HTTPError, KeyError, RuntimeError, ValueError) as exc:
        logger.error(
            "Auto Merge 실패 (repo=%s, pr=%d): %s",
            repo_name, pr_number, type(exc).__name__,
        )


async def _handle_terminal_merge_failure(  # pylint: disable=too-many-arguments
    *,
    config: RepoConfigData,
    github_token: str,
    repo_name: str,
    pr_number: int,
    score: int,
    reason: str | None,
    reason_tag: str,
    analysis_id: int | None,
    db: Session | None,
) -> None:
    """터미널 머지 실패: MergeAttempt 기록 + 알림 + 선택적 GitHub Issue 생성.
    Terminal merge failure: log MergeAttempt + notify + optionally create GitHub issue.
    """
    if analysis_id is not None and db is not None:
        try:
            log_merge_attempt(
                db,
                analysis_id=analysis_id,
                repo_name=repo_name,
                pr_number=pr_number,
                score=score,
                threshold=config.merge_threshold,
                success=False,
                reason=reason,
            )
        except Exception as log_exc:  # pylint: disable=broad-except
            logger.warning("merge_attempt 기록 실패: %s", log_exc)

    # 3-layer 사용자 언어 결정 (User → RepoConfig → settings.default_locale)
    # 사이클 149 Sprint 3 — get_advice 도 동일 언어 적용 (조언 텍스트 i18n)
    # 3-layer language resolve; Cycle 149 Sprint 3 — advice text also localized
    from src.notifier._language import resolve_notification_language  # noqa: WPS433  # pylint: disable=import-outside-toplevel
    with SessionLocal() as db_lang:
        language = resolve_notification_language(db_lang, config=config)
    advice = get_advice(reason_tag, language)
    logger.warning(
        "PR #%d auto-merge 실패 (repo=%s): %s",
        pr_number, sanitize_for_log(repo_name), sanitize_for_log(reason),
    )
    await _notify_merge_failure(
        repo_name=repo_name,
        pr_number=pr_number,
        score=score,
        threshold=config.merge_threshold,
        reason=reason or "unknown",
        advice=advice,
        chat_id=config.notify_chat_id or settings.telegram_chat_id,
        language=language,
    )
    if config.auto_merge_issue_on_failure:
        try:
            await create_merge_failure_issue(
                github_token=github_token,
                repo_name=repo_name,
                pr_number=pr_number,
                score=score,
                threshold=config.merge_threshold,
                reason=reason or "unknown",
                advice=advice,
                language=language,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning(
                "create_merge_failure_issue 실패 (pr=%d): %s", pr_number, exc
            )


async def _notify_merge_failure(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason: str,
    advice: str,
    chat_id: str | None,
    language: str = "ko",
) -> None:
    """auto_merge 실패를 Telegram 으로 알린다. chat_id 없으면 스킵.

    Notify auto_merge failure via Telegram; skip when chat_id is missing.
    사이클 152 Sprint 2 — 하드코딩 한국어 → i18n (language 기반 get_text 조합).
    Cycle 152 Sprint 2 — hardcoded Korean replaced with language-aware get_text.
    """
    if not chat_id or not settings.telegram_bot_token:
        return
    # Phase F QW3: GitHub PR 링크 추가 — 사용자 즉시 접근
    pr_url = f"https://github.com/{repo_name}/pull/{pr_number}"
    text = (
        get_text("notifier.gate.merge_failed_title", language) + "\n"
        + get_text("notifier.gate.retry_repo_line", language, repo=escape(repo_name), pr=pr_number) + "\n"
        + get_text("notifier.gate.merge_score_threshold", language, score=score, threshold=threshold) + "\n"
        + get_text("notifier.gate.merge_reason_line", language, reason=escape(reason)) + "\n"
        + get_text("notifier.gate.merge_advice_line", language, advice=escape(advice)) + "\n"
        + get_text("notifier.gate.merge_view_github", language, url=escape(pr_url))
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token,
            chat_id,
            {"text": text, "parse_mode": "HTML"},
        )
    except httpx.HTTPError as exc:
        logger.warning("Telegram merge-failure 알림 실패: %s", exc)


async def _notify_merge_deferred(
    *,
    repo_name: str,
    pr_number: int,
    score: int,
    threshold: int,
    reason_tag: str,
    ci_status: str,
    chat_id: str | None,
    language: str = "ko",
) -> None:
    """CI 대기 중임을 사용자에게 알린다 (최초 지연 1회).
    Notify user that merge is deferred while waiting for CI (first deferral only).

    사이클 152 Sprint 2 — 하드코딩 한국어 → i18n (language 기반 get_text 조합).
    Cycle 152 Sprint 2 — hardcoded Korean replaced with language-aware get_text.
    """
    if not chat_id or not settings.telegram_bot_token:
        return
    msg = (
        get_text("notifier.gate.merge_deferred_title", language) + "\n"
        + get_text("notifier.gate.retry_repo_line", language, repo=escape(repo_name), pr=pr_number) + "\n"
        + get_text("notifier.gate.merge_deferred_score", language, score=score, threshold=threshold) + "\n"
        + get_text(
            "notifier.gate.merge_deferred_reason", language,
            ci_status=ci_status, reason=escape(reason_tag),
        ) + "\n"
        + get_text("notifier.gate.merge_deferred_retry", language)
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token,
            chat_id,
            {"text": msg, "parse_mode": "HTML"},
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("_notify_merge_deferred 전송 실패: %s", type(exc).__name__)
