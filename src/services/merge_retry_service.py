"""merge_retry_service — pending 재시도 큐 처리 워커 (Phase 12 T9).
merge_retry_service — worker that processes the pending merge retry queue (Phase 12 T9).

claim_batch → 각 행별 GitHub token 조회 → 설정 재확인 → PR 상태 사전 검사
→ merge_pr 호출 → 결과에 따라 succeeded / terminal / released 분기.
claim_batch → per-row GitHub token resolution → config re-check → PR pre-flight
→ call merge_pr → branch to succeeded / terminal / released based on result.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.config import settings
from src.config_manager.manager import RepoConfigData, get_repo_config
from src.constants import GITHUB_API
from src.gate import merge_reasons
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
from src.i18n.loader import get_text
from src.models.merge_retry import MergeRetryQueue
from src.notifier._language import resolve_notification_language
from src.notifier.merge_failure_issue import create_merge_failure_issue
from src.notifier.telegram import telegram_post_message
from src.repositories import merge_retry_repo, repository_repo, user_repo
from src.shared.http_client import get_http_client
from src.gate import _merge_attempt_states as _states
from src.shared.merge_metrics import log_merge_attempt
from src.shared.off_loop import run_blocking
from src.shared.time_utils import to_naive_utc
from src.shared.http_client import HTTPX_SEND_ERRORS

logger = logging.getLogger(__name__)

# 재시도 알림 메시지의 repo 라인 i18n 키 (3곳 공통 — S1192 중복 리터럴 상수화)
# i18n key for the repo line in retry notification messages (shared by 3 call sites)
_RETRY_REPO_LINE_KEY = "notifier.gate.retry_repo_line"


async def process_pending_retries(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 50,
    only_ids: list[int] | None = None,
) -> dict[str, int]:
    """pending 재시도 큐를 처리한다.
    Process the pending merge retry queue.

    Returns counts dict: {"claimed", "succeeded", "terminal", "abandoned", "released", "skipped"}
    사이클 93 PR-B: 단일 row 처리 = `_process_single_retry` 분리 (S3776 26→<15).
    Cycle 93 PR-B: per-row processing extracted to `_process_single_retry` (S3776 26→<15).

    🔴 동기 DB 는 전부 워커 스레드에서(`run_blocking`) — 루프에는 GitHub·Telegram await 만 남는다.
    운영(왕복 ≈ 0.2 s)에서 빈 큐 claim 만으로 1분마다 루프가 ≈ 0.78 s 섰다. 세션은 한 번에 한
    스레드만 쓴다(순차 인계 — 취소가 와도 스레드가 끝날 때까지 기다린다). ORM 행은 루프에서 읽지
    않는다 — 커밋이 만료시킨 속성을 읽는 순간 SELECT 가 루프에서 돈다(`_RowView`).
    All sync DB runs in worker threads; only the GitHub/Telegram awaits stay on the loop. The session
    is handed over one thread at a time, and the loop never reads an ORM row.
    """
    # 현재 시각 설정 — 테스트에서 주입 가능 (freezegun 불필요)
    # Set current time — injectable from tests (no freezegun needed)
    now = now or datetime.now(timezone.utc)

    # 처리 가능한 행을 원자적으로 클레임 (attempts_count += 1 포함) + (행, id, 토큰) 값 스냅샷
    # Atomically claim processable rows (includes attempts_count += 1) + snapshot (row, id, token)
    claimed = await run_blocking(
        _claim_batch_snapshot, db, now=now, limit=limit, only_ids=only_ids,
    )

    counts: dict[str, int] = {
        "claimed": len(claimed),
        "succeeded": 0,
        "terminal": 0,
        "expired": 0,
        "abandoned": 0,
        "released": 0,
        "skipped": 0,
    }

    for row, row_id, claim_token in claimed:
        try:
            await _process_single_retry(db, row, now, counts, claim_token=claim_token)
        except (*HTTPX_SEND_ERRORS, SQLAlchemyError) as exc:
            # 인프라 에러 — 클레임 해제, 짧은 백오프, attempts_count 미증가
            # Infra error — release claim, short backoff, do NOT bump attempts_count
            logger.warning(
                "retry worker infra error row_id=%d: %s", row_id, type(exc).__name__
            )
            await run_blocking(
                _recover_and_release, db, row, now, counts, reason="infra_error", exc=exc,
                expected_claim_token=claim_token,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
            # 예상외 단일 행 결함(KeyError/ValueError 등) 격리 — 전체 배치 중단 방지(C3).
            # Isolate an unexpected single-row failure so it can't abort the whole batch (C3).
            logger.exception("retry worker unexpected error row_id=%d", row_id)
            await run_blocking(
                _recover_and_release, db, row, now, counts, reason="unexpected_error", exc=exc,
                expected_claim_token=claim_token,
            )

    return counts


def _claim_batch_snapshot(
    db: Session, *, now: datetime, limit: int, only_ids: list[int] | None,
) -> list[tuple[MergeRetryQueue, int, str | None]]:
    """클레임하고 행마다 (행, id, 소유권 토큰) 을 **값으로** 스냅샷한다(워커 스레드에서).

    Claim, then snapshot (row, id, ownership token) as VALUES per row (in a worker thread).

    🔴 소유권 토큰은 **배치 반환 직후 값으로** 스냅샷한다 (2026-07-31 다관점 검증 P1 — 실측 재현).
      이전 판은 루프 안에서 `row.claim_token` 을 읽었는데, `sessionmaker` 가 `expire_on_commit`
      을 지정하지 않아(기본 True) **직전 행의 write-back commit 이 세션 전체를 만료**시킨다.
      그래서 rows 2..N 의 "캡처" 는 사실 **DB 재조회**이고, 그 사이 다른 워커가 stale(>300s)
      재클레임했다면 캡처값 = **그 워커의 토큰**이 된다. 결과: 이 워커가 남의 claim 을 해제하고,
      정당한 소유자의 `mark_terminal` 이 CAS 0행 매치로 거부돼 **종결 결과가 소실되고 행이
      `pending` 으로 부활**한다 — CAS 가 막으려던 실패 모드가 소유자 쪽으로 뒤집힌 것이다.
      기본 batch=50 에서 **49/50 행이 무방비**였다.
    🔴 id 도 같은 이유로 값으로 둔다 — 만료된 행의 `row.id` 도 SELECT 다(루프에서 읽으면 루프 SQL).
    Snapshot ownership tokens (and ids) as VALUES before any per-row commit: expire_on_commit
    defaults to True, so reading them later is a DB re-read for rows 2..N.
    """
    claimed = merge_retry_repo.claim_batch(
        db,
        now=to_naive_utc(now),
        limit=limit,
        stale_after_seconds=300,
        only_ids=only_ids,
    )
    return [(row, row.id, row.claim_token) for row in claimed]


@dataclass(frozen=True)
class _RowView:  # pylint: disable=too-many-instance-attributes  # 큐 행 컬럼 사본 / column copy
    """루프가 읽는 큐 행 값 — 행 처리 첫머리에 워커 스레드에서 한 번 복사한다.

    Queue-row values the loop reads, copied once in a worker thread when the row's turn starts.

    🔴 ORM 행을 루프에서 읽지 않는다 — 행마다 write-back 이 커밋하고 세션은 `expire_on_commit`
    기본값이라, 만료된 속성을 읽는 순간 SELECT 가 루프 스레드에서 돈다. 복사 시점은 종전의 첫
    속성 읽기와 같다(직전 행의 커밋이 만료시킨 행을 그때 다시 읽는다) — 판정에 쓰는 값은 그대로다.
    The copy happens where the old code first read the row, so decisions see the same values.
    """

    id: int
    repo_full_name: str
    pr_number: int
    analysis_id: int
    commit_sha: str
    score: int
    threshold_at_enqueue: int
    attempts_count: int
    max_attempts: int
    notify_chat_id: str | None
    created_at: datetime | None


def _row_view(row) -> _RowView:
    """ORM 행(또는 같은 속성의 대역)에서 `_RowView` 값을 복사한다 — 워커 스레드에서만 부른다.
    Copy `_RowView` values from a row (or a stand-in with the same attributes); worker thread only."""
    return _RowView(**{f.name: getattr(row, f.name) for f in fields(_RowView)})


@dataclass(frozen=True)
class _Preflight:
    """토큰·설정 확인을 통과한 행 — 루프가 이어서 쓸 값만 담는다.
    A row past the token/config checks, holding only what the loop needs next."""

    view: _RowView
    claim_token: str | None
    token: str
    cfg: RepoConfigData
    language: str
    config_changed: bool


def _recover_and_release(db: Session, row, now: datetime, counts: dict[str, int],
                         *, reason: str, exc: Exception,
                         expected_claim_token: str | None = None) -> None:
    """실패한 행의 세션을 복구하고 클레임을 안전하게 해제한다 — 두 except 핸들러 공용.

    Recover the session and safely release a failed row's claim — shared by both handlers.

    🔴 이 헬퍼 도입 전에는 좁은 except(infra_error)와 넓은 except(unexpected_error)가 복구 로직을
    각자 인라인으로 두어 **드리프트**했다 — 좁은 쪽만 `db.rollback()`·status 가드가 없어, 커밋 실패로
    오염된 세션에서 `release_claim` 의 UPDATE 가 PendingRollbackError 로 for-loop 전체를 중단시켰다
    (claimed 잔여 행이 5분 stale 까지 묶임). 단일 헬퍼로 통합해 그 비대칭을 원천 차단 (준비도 감사 #10).
    🔴 Before this helper, the two handlers inlined their recovery and drifted — only the narrow one
    lacked rollback + the status guard, so release_claim on a poisoned session aborted the batch.

    복구 3단계:
    1. `db.rollback()` — 커밋 실패로 오염된 세션 복구 (release_claim 쿼리의 PendingRollbackError 차단)
    2. `status == "pending"` 가드 — terminal(succeeded 등) 로 이미 커밋된 뒤 부수효과에서 예외가 났으면
       그 완료 행의 `last_failure_reason` 을 덮어쓰지 않는다 (감사 추적 오염·재시도 부활 차단).
    3. 해제 자체 실패도 격리 — 배치는 계속 (5분 stale 재클레임이 안전망).

    🔴 expected_claim_token (P1-5): 호출자 loop 가 처리 前 캡처한 원본 토큰. `db.refresh(row)` 는
    row 를 DB 최신값으로 덮어써 재클레임 시 새 토큰이 실리므로, refresh 로는 원본 소유권을 알 수 없다
    → loop 에서 캡처한 원본 토큰을 CAS 조건으로 넘겨, 다른 워커가 재클레임한 행을 이 워커가 되돌리지
    못하게 한다(released 카운트도 실제 해제 시에만 증가).
    Threads the pre-refresh ownership token captured by the caller loop, since db.refresh overwrites
    row with the reclaiming worker's token; CAS ensures we never revert a row another worker owns.
    동기 DB 라 호출자는 워커 스레드에서 부른다(`run_blocking`). / Callers run it in a worker thread.
    """
    try:
        db.rollback()
        db.refresh(row)
        if row.status == "pending":
            released = merge_retry_repo.release_claim(
                db,
                row.id,
                next_retry_at=to_naive_utc(now) + timedelta(seconds=30),
                last_failure_reason=reason,
                last_detail_message=str(exc)[:200],
                expected_claim_token=expected_claim_token,
            )
            if released:
                counts["released"] += 1
    except Exception:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # 클레임 해제 자체 실패해도 배치는 계속 (다음 행 처리). 5분 stale 재클레임이 안전망.
        # Even if claim release fails, keep the batch going; the 5-min stale reclaim is the net.
        logger.exception("retry worker: claim release failed row_id=%d", row.id)


async def _process_single_retry(
    db: Session,
    row,
    now: datetime,
    counts: dict[str, int],
    *,
    claim_token: str | None = None,
) -> None:
    """단일 retry row 처리 — 사이클 93 PR-B (S3776 26→<15 분리).

    Process a single retry row (Cycle 93 PR-B — extracted from process_pending_retries).
    counts dict 직접 mutate. 호출자 (process_pending_retries) 가 try/except wrap.
    동기 DB 단계(`_preflight_retry`·`_settle_before_merge`·`_record_merged`)는 워커 스레드에서,
    GitHub·Telegram await 는 루프에서 — 순서는 종전과 같다.
    Sync DB phases run in worker threads and the HTTP awaits on the loop, in the same order as before.
    """
    # 🔴 소유권 토큰 캡처 (종합감사 P1-5) — claim_batch 가 이 워커에게 부여한 claim_token.
    # 이 함수의 모든 write-back(mark_*/release_claim/_handle_merge_failure)에 CAS 조건으로 전달해,
    # 처리 도중 batch 가 stale 임계(300s)를 넘겨 다른 워커가 재클레임하면(토큰 변경) 이 워커의
    # 뒤늦은 write-back 이 no-op 되게 한다.
    # 🔴 **정확한 범위 (2026-07-24 회고 P2-M + Grok claim-review REFUTED 정정)**: CAS 는 큐 행
    #   write-back 의 **낙관적 동시성(DB 상태 clobber 차단)** 이다 — "이중 처리 전면 차단"이 아니다.
    #   CAS miss 여도 이 워커는 이미 `merge_pr`(실제 머지)·`log_merge_attempt`·notify 를 호출한 뒤다.
    #   실제 이중 **머지**는 GitHub 멱등성(이미 머지됨→ALREADY_MERGED) + sha_drift/expected_sha 가 막고,
    #   CAS 는 stale 워커가 B 의 종결 상태를 덮어써 재시도를 부활시키는 것을 막는다. 잔여 = 중복 notify·
    #   counts 과대(진단 지표, 제어 흐름 무관) — 낙관적 동시성의 수용된 한계.
    # CAS = optimistic concurrency on queue write-backs (DB clobber prevention), NOT full
    #   double-processing prevention: on a CAS miss the worker has already called merge_pr/notify;
    #   the actual double-merge is prevented by GitHub idempotency + the sha/expected_sha guards.
    # 🔴 호출자가 **배치 반환 직후** 스냅샷한 값을 받는다 (2026-07-31 다관점 검증 P1).
    #   `row.claim_token` 을 읽으면 직전 행의 commit 이 세션을 만료시킨 뒤라 DB 재조회가 되고,
    #   그 사이 다른 워커가 재클레임했으면 **남의 토큰**을 자기 것으로 착각한다.
    #   `claim_token=None` 폴백은 호출자 미지정(구 호출부·직접 테스트) 대비 — 그 경우 종전 동작.
    # Receives the value snapshotted right after claim_batch; reading row.claim_token here would be
    # a DB re-read (expire_on_commit) and could pick up another worker's token.
    pre = await run_blocking(_preflight_retry, db, row, now, counts, claim_token)
    if pre is None:
        return
    view = pre.view
    if pre.config_changed:
        await _notify_config_changed(view, pre.cfg, language=pre.language)
        counts["abandoned"] += 1
        return

    # ── c. PR 사전 검사 (D7) ──────────────────────────────────────
    pr_data = await _get_pr_data(pre.token, view.repo_full_name, view.pr_number)
    if await run_blocking(_settle_before_merge, db, pre, pr_data, now, counts):
        return

    # ── d. merge_pr 호출 ──────────────────────────────────────────
    # 🔴 감사 ③ — SHA-bound 불변식: retry 경로는 2nd-LLM 검증자(merge_verifier)를 재실행하지 않는다
    # (검증은 초기 _run_auto_merge 진입부에서 1회). 그래도 안전한 이유 = 이 경로가 (1) 위 sha_drift
    # 검사(head_sha != row.commit_sha → abandon)와 (2) `expected_sha=row.commit_sha` 전달로 GitHub
    # 측 SHA 원자성(#962)을 보장하므로, retry 는 '검증자가 승인한 정확히 동일한 SHA' 만 머지할 수 있다.
    # 동일 커밋은 diff/리뷰 요약이 불변이라 검증자 verdict 가 stale 될 수 없다. expected_sha 바인딩을
    # 제거하면 force-push 된 미검증 코드가 머지될 수 있으니 절대 빼지 말 것
    # (회귀 가드: test_merge_retry_service.py::test_retry_passes_expected_sha_binds_to_queued_commit).
    # Audit ③ — SHA-bound invariant: the retry path does NOT re-run the 2nd-LLM verifier (verification
    # happens once at the initial _run_auto_merge). It is still safe because this path (1) aborts on
    # sha_drift above and (2) passes expected_sha=row.commit_sha for GitHub-side SHA atomicity (#962),
    # so a retry can only ever merge the exact SHA the verifier approved — and a fixed commit's diff /
    # review summary cannot change, so the verdict cannot go stale. Never drop the expected_sha binding.
    ok, reason, _ = await merge_pr(
        pre.token, view.repo_full_name, view.pr_number, expected_sha=view.commit_sha,
    )

    # ── e. 성공 처리 ──────────────────────────────────────────────
    if ok:
        await run_blocking(_record_merged, db, pre)
        await _notify_merge_succeeded(view, pre.cfg, language=pre.language)
        counts["succeeded"] += 1
        return

    # ── f. 실패 처리 (terminal/expired/transient 분류 + 로깅·알림·큐 복귀) ──
    await _handle_merge_failure(
        db, row=view, cfg=pre.cfg, token=pre.token, pr_data=pr_data,
        reason=reason, now=now, language=pre.language, counts=counts,
        expected_claim_token=pre.claim_token,
    )


def _preflight_retry(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    db: Session, row, now: datetime, counts: dict[str, int], claim_token: str | None,
) -> _Preflight | None:
    """시도 한도·토큰·설정 확인(a-0·a·b) — 워커 스레드에서. 여기서 끝난 행은 None.

    Attempt cap, token and config checks (a-0, a, b) in a worker thread; None when the row is done.
    설정 변경 행은 기록·마킹까지 하고 `config_changed=True` 로 돌려준다 — 알림 await 는 루프 몫이다.
    A config-changed row is logged and marked here; the loop sends its notification.
    """
    view = _row_view(row)
    tok = claim_token if claim_token is not None else row.claim_token
    # ── a-0. 최대 시도 횟수 초과 (🔴 토큰 조회 前 — no_token 무한루프 방지, 종합감사 P1-11) ──
    # claim 시 attempts_count 가 선증가하므로(merge_retry_repo.claim_batch) 이 검사는 merge_pr 호출 이전 단계다.
    # 따라서 max_attempts=N 설정 시 실제 머지 시도는 N-1회 — 의도된 fail-safe(시도 횟수가 적은 보수적 방향).
    # 🔴 이 검사는 **토큰 조회보다 먼저** 와야 한다: 소유자가 GitHub 연결 해제/PAT 로테이션 하고
    # 전역 GITHUB_TOKEN 도 없으면, 아래 no_token release 가 매번 return 해 이 cap 에 영영 도달 못 해
    # 30초 간격 무한 재시도가 된다(attempts_count 는 claim 마다 증가하나 소진 판정 미도달). cap 을
    # 위로 올리면 no_token 행도 max_attempts 후 abandon 된다.
    # attempts_count is pre-incremented at claim time (runs BEFORE merge_pr, so N=N-1 tries — fail-safe).
    # 🔴 This cap MUST precede token resolution: a persistently token-less repo would otherwise return at
    # the no_token release every cycle and never reach the cap → infinite 30s retry loop.
    if view.attempts_count >= view.max_attempts:
        # 🔴 종결 전 MergeAttempt 미러링 — merge_retry_queue 7일 GC(#1075) 후에도 최종 결과 이력
        # 보존(회고 P2#17). cfg 미조회 시점이라 threshold 는 enqueue 스냅샷 사용(이 경로는 live-merge
        # 게이팅이 없어 C11 live-threshold 근거가 무관 — max_attempts 는 순수 재시도 소진).
        # Mirror to MergeAttempt before the terminal GC so the outcome survives the 7-day sweep (#1075).
        log_merge_attempt(
            db, analysis_id=view.analysis_id, repo_name=view.repo_full_name,
            pr_number=view.pr_number, score=view.score,
            threshold=view.threshold_at_enqueue, success=False, reason="max_attempts_exceeded",
        )
        merge_retry_repo.mark_abandoned(
            db, view.id, reason="max_attempts_exceeded", expected_claim_token=tok,
        )
        counts["abandoned"] += 1
        return None

    # ── a. GitHub 토큰 조회 ────────────────────────────────────────
    token = _resolve_github_token(db, view.repo_full_name)
    if token is None:
        # 토큰 없음 — 30초 후 재시도 대기로 복귀 (위 a-0 cap 이 무한루프를 종결시킨다)
        # No token — release back to retry queue after 30s (the a-0 cap above bounds the loop)
        merge_retry_repo.release_claim(
            db, view.id, next_retry_at=to_naive_utc(now) + timedelta(seconds=30),
            last_failure_reason="no_token", expected_claim_token=tok,
        )
        counts["released"] += 1
        return None

    # ── b. 설정 재확인 (D5) ────────────────────────────────────────
    cfg = get_repo_config(db, view.repo_full_name)
    # 사이클 149 Sprint 4 — 알림 사용자 언어 결정 (재시도 알림 텍스트 i18n)
    # Cycle 149 Sprint 4 — resolve user language for retry notification text i18n
    language = resolve_notification_language(db, config=cfg)
    config_changed = not (cfg.auto_merge and view.score >= cfg.merge_threshold)
    if config_changed:
        # 설정이 변경되어 자동 머지 조건 미충족 → 포기 (알림은 호출자가 루프에서)
        # Config changed so auto-merge condition no longer met → abandon (the caller notifies)
        # 🔴 종결 전 MergeAttempt 미러링 (회고 P2#17) — live cfg.merge_threshold(C11 결정).
        log_merge_attempt(
            db, analysis_id=view.analysis_id, repo_name=view.repo_full_name,
            pr_number=view.pr_number, score=view.score,
            threshold=cfg.merge_threshold, success=False, reason=merge_reasons.CONFIG_CHANGED,
        )
        merge_retry_repo.mark_abandoned(
            db, view.id, reason=merge_reasons.CONFIG_CHANGED, expected_claim_token=tok,
        )
    return _Preflight(view=view, claim_token=tok, token=token, cfg=cfg, language=language,
                      config_changed=config_changed)


def _settle_before_merge(
    db: Session, pre: _Preflight, pr_data: dict | None, now: datetime, counts: dict[str, int],
) -> bool:
    """PR 사전 검사 결과로 머지 전에 끝나는 행을 기록한다(c) — 워커 스레드에서. 끝났으면 True.

    Record rows that end before the merge call (c) in a worker thread; True when the row is done.
    """
    view, tok, cfg = pre.view, pre.claim_token, pre.cfg
    if pr_data is None:
        merge_retry_repo.release_claim(
            db, view.id, next_retry_at=to_naive_utc(now) + timedelta(seconds=30),
            last_failure_reason="pr_fetch_failed", expected_claim_token=tok,
        )
        counts["released"] += 1
        return True

    # 이미 머지된 PR — 성공
    if pr_data.get("merged") is True:
        # 🔴 종결 전 MergeAttempt 미러링 (회고 P2#17) — PR 이 머지된 최종 상태 = success=True.
        # 🔴 `state` 를 반드시 넘긴다 (2026-08-24). 기본값은 `legacy` 이고, 이 워커가
        #    **운영의 primary 머지 경로**라 그 기본값이 머지 실적 대부분을 라벨 없는 상태로
        #    남겨 왔다 — 실측: success=True 733행 중 675행이 `legacy`.
        #    머지율 KPI 가 state 를 보게 되면 그 행들이 통째로 사라진다.
        # The retry worker is the production primary merge path; leaving `state` at its
        # default made most real merges unlabelled.
        log_merge_attempt(
            db, analysis_id=view.analysis_id, repo_name=view.repo_full_name,
            pr_number=view.pr_number, score=view.score,
            threshold=cfg.merge_threshold, success=True, reason=None,
            state=_states.DIRECT_MERGED, merged_at=to_naive_utc(datetime.now(timezone.utc)),
        )
        merge_retry_repo.mark_succeeded(
            db, view.id, reason=merge_reasons.ALREADY_MERGED, expected_claim_token=tok,
        )
        counts["succeeded"] += 1
        return True

    # SHA drift — force-push 감지
    # head 키가 present-but-None 일 수 있어 `or {}` 정규화 (PR #124 패턴)
    # head key may be present-but-None — normalize with `or {}` (PR #124 pattern)
    head_sha = (pr_data.get("head") or {}).get("sha", "")
    if head_sha and head_sha != view.commit_sha:
        # 🔴 종결 전 MergeAttempt 미러링 (회고 P2#17) — force-push 로 포기, live threshold(C11).
        log_merge_attempt(
            db, analysis_id=view.analysis_id, repo_name=view.repo_full_name,
            pr_number=view.pr_number, score=view.score,
            threshold=cfg.merge_threshold, success=False, reason=merge_reasons.SHA_DRIFT,
        )
        merge_retry_repo.mark_abandoned(
            db, view.id, reason=merge_reasons.SHA_DRIFT, expected_claim_token=tok,
        )
        counts["abandoned"] += 1
        return True
    return False


def _record_merged(db: Session, pre: _Preflight) -> None:
    """머지 성공 기록(e) — 워커 스레드에서. 알림 await 는 호출자가 루프에서.
    Record a successful merge (e) in a worker thread; the caller notifies on the loop."""
    view = pre.view
    # 🔴 `state=DIRECT_MERGED` — REST `merge_pr()` 즉시 성공이 이 state 의 정의다
    #    (`_merge_attempt_states`). 위 관측 경로와 같은 이유로 기본값에 맡기지 않는다.
    log_merge_attempt(
        db, analysis_id=view.analysis_id, repo_name=view.repo_full_name,
        pr_number=view.pr_number, score=view.score,
        threshold=pre.cfg.merge_threshold, success=True, reason=None,
        state=_states.DIRECT_MERGED, merged_at=to_naive_utc(datetime.now(timezone.utc)),
    )
    merge_retry_repo.mark_succeeded(db, view.id, expected_claim_token=pre.claim_token)


# ---------------------------------------------------------------------------
# Private helpers
# 비공개 헬퍼 함수
# ---------------------------------------------------------------------------


async def _handle_merge_failure(  # pylint: disable=too-many-arguments,too-many-locals
    db: Session, *, row, cfg: RepoConfigData, token: str, pr_data: dict,
    reason: str, now: datetime, language: str, counts: dict[str, int],
    expected_claim_token: str | None = None,
) -> None:
    """merge_pr 실패 후 처리 — terminal/expired/transient 분류 + 로깅·알림·큐 복귀.

    Handle a failed merge_pr outcome: classify terminal/expired/transient, log, notify, requeue.
    `_process_single_retry` 의 실패 경로(f/g)를 분리 — 인지 복잡도 감소.
    🔴 expected_claim_token (P1-5): 호출자 `_process_single_retry` 가 캡처한 소유권 토큰을 받아 여기
    3개 write-back(mark_terminal/mark_expired/release_claim)에도 CAS 조건으로 전달 — 재클레임 시 no-op.
    Receives the caller's ownership token and threads it to all 3 write-backs as a CAS guard.
    `row` 는 루프에서 읽어도 되는 값(`_RowView`)이고, DB 쓰기는 워커 스레드에서 한다.
    `row` is loop-safe values (`_RowView`); the DB writes run in a worker thread.
    """
    reason_tag = parse_reason_tag(reason)
    # F1: pr_data 에 이미 base.ref 가 있으므로 추가 호출 없이 활용
    # base 키가 present-but-None 일 수 있어 `or {}` 정규화 (PR #124 패턴)
    # base key may be present-but-None — normalize with `or {}` (PR #124 pattern)
    base_ref = (pr_data.get("base") or {}).get("ref", "main")
    ci_status = await _get_ci_status_safe(
        token, row.repo_full_name, row.commit_sha, base_ref=base_ref,
    )
    expired = is_expired(row, now=now, max_age_hours=settings.merge_retry_max_age_hours)

    is_terminal_failure = not should_retry(reason_tag, ci_status)
    if is_terminal_failure or expired:
        # 재시도 불가(terminal) 또는 max_age 초과(expired) → 재시도 중단
        # 두 경우를 상태로 구분: 실제 종료 실패는 failed_terminal, 재시도 가능했으나
        # 만료된 행은 'expired' (정합성 감사 P1 — mark_expired dead code 활성화, 오기록 방지).
        # Non-retriable (terminal) or aged out (expired) → stop retrying. Distinguish by status:
        # a genuine terminal failure → failed_terminal; a retriable row that aged out → 'expired'.
        await run_blocking(
            _record_retry_stop, db, row, cfg, reason, reason_tag,
            terminal=is_terminal_failure, expected_claim_token=expected_claim_token,
        )
        counts["terminal" if is_terminal_failure else "expired"] += 1
        # 사이클 149 Sprint 3/4 — 알림 + Issue 사용자 언어 (상단 b 단계에서 결정)
        # Cycle 149 Sprint 3/4 — user language for notify + Issue (resolved in step b above)
        await _notify_merge_terminal(row, cfg, reason, reason_tag, language=language)
        if cfg.auto_merge_issue_on_failure:
            await _create_failure_issue_safe(token, row, cfg, reason, reason_tag, language=language)
        return

    # ── 일시적 실패 — 백오프 후 재시도 대기로 복귀 ────────────
    next_retry_at = compute_next_retry_at(
        row.attempts_count,
        now=now,
        initial_backoff=settings.merge_retry_initial_backoff_seconds,
        max_backoff=settings.merge_retry_max_backoff_seconds,
    )
    await run_blocking(
        merge_retry_repo.release_claim, db, row.id,
        next_retry_at=to_naive_utc(next_retry_at),  # naive UTC for DB
        last_failure_reason=reason_tag, last_detail_message=reason,
        expected_claim_token=expected_claim_token,
    )
    counts["released"] += 1


def _record_retry_stop(  # pylint: disable=too-many-arguments,too-many-positional-arguments
    db: Session, row, cfg: RepoConfigData, reason: str, reason_tag: str,
    *, terminal: bool, expected_claim_token: str | None,
) -> None:
    """재시도 중단 기록 — MergeAttempt 미러링 + failed_terminal/expired 마킹(워커 스레드에서).
    Record a stopped retry — mirror to MergeAttempt, then mark failed_terminal/expired (worker thread)."""
    log_merge_attempt(
        db, analysis_id=row.analysis_id, repo_name=row.repo_full_name,
        pr_number=row.pr_number, score=row.score,
        threshold=cfg.merge_threshold, success=False, reason=reason,
    )
    if terminal:
        merge_retry_repo.mark_terminal(
            db, row.id, reason=reason_tag, expected_claim_token=expected_claim_token,
        )
    else:
        # 재시도 가능했으나 max_age 초과 — terminal 실패와 구분해 'expired' 기록
        merge_retry_repo.mark_expired(
            db, row.id, reason=reason_tag, expected_claim_token=expected_claim_token,
        )


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
    url = f"{GITHUB_API}/repos/{repo_full_name}/pulls/{pr_number}"
    try:
        client = get_http_client()
        r = await client.get(url, headers=github_api_headers(token))
        r.raise_for_status()
        return r.json()
    except HTTPX_SEND_ERRORS:
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
    # BPR 조회는 통신 오류를 **전파하지 않는다** (engine.py 쌍둥이와 동일).
    # handler 를 두면 죽은 코드다 — 근거는
    # tests/unit/github_client/test_bpr_never_propagates_transport_errors.py.
    #
    # The BPR fetch swallows transport errors; a handler here would be unreachable.
    required = await get_required_check_contexts(token, repo_full_name, base_ref)

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
    except HTTPX_SEND_ERRORS:
        return "unknown"


def _resolve_retry_chat_id(row: MergeRetryQueue, cfg: RepoConfigData) -> str | None:
    """retry worker 알림 chat_id 3-tier fallback (config → row 스냅샷 → global).

    Resolve retry worker notification chat_id (3-tier fallback).
    `analytics_service.resolve_chat_id` 와 분리: row.notify_chat_id 단계 추가.
    """
    return cfg.notify_chat_id or row.notify_chat_id or settings.telegram_chat_id


async def _notify_config_changed(
    row: MergeRetryQueue, cfg: RepoConfigData, *, language: str = "ko"
) -> None:
    """설정 변경으로 재시도가 중단됐음을 알린다.
    Notify user that retry was stopped due to config change.
    """
    chat_id = _resolve_retry_chat_id(row, cfg)
    if not chat_id or not settings.telegram_bot_token:
        return
    # HTML 태그는 키 값에 보존, 동적 값(repo)만 escape 후 kwargs 전달
    # HTML tags kept in key values; only dynamic value (repo) escaped before kwargs
    msg = (
        get_text("notifier.gate.retry_stopped_title", language) + "\n"
        + get_text(
            _RETRY_REPO_LINE_KEY, language,
            repo=escape(row.repo_full_name), pr=row.pr_number,
        ) + "\n"
        + get_text("notifier.gate.retry_stopped_reason", language)
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token, chat_id, {"text": msg, "parse_mode": "HTML"}
        )
    except HTTPX_SEND_ERRORS as exc:
        logger.warning("_notify_config_changed 전송 실패: %s", type(exc).__name__)


async def _notify_merge_succeeded(
    row: MergeRetryQueue, cfg: RepoConfigData, *, language: str = "ko"
) -> None:
    """재시도 후 머지 성공을 알린다 (시도 횟수 포함).
    Notify user of successful merge after retries (includes attempt count).
    """
    chat_id = _resolve_retry_chat_id(row, cfg)
    if not chat_id or not settings.telegram_bot_token:
        return
    pr_url = f"https://github.com/{row.repo_full_name}/pull/{row.pr_number}"
    # HTML 태그는 키 값에 보존, 동적 값(repo/url)만 escape 후 kwargs 전달
    # HTML tags kept in key values; only dynamic values (repo/url) escaped
    msg = (
        get_text("notifier.gate.retry_succeeded_title", language) + "\n"
        + get_text(
            _RETRY_REPO_LINE_KEY, language,
            repo=escape(row.repo_full_name), pr=row.pr_number,
        ) + "\n"
        + get_text(
            "notifier.gate.retry_score_attempts", language,
            score=row.score, attempts=row.attempts_count,
        ) + "\n"
        + get_text("notifier.gate.retry_view_github", language, url=escape(pr_url))
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token, chat_id, {"text": msg, "parse_mode": "HTML"}
        )
    except HTTPX_SEND_ERRORS as exc:
        logger.warning("_notify_merge_succeeded 전송 실패: %s", type(exc).__name__)


async def _notify_merge_terminal(
    row: MergeRetryQueue,
    cfg: RepoConfigData,
    reason: str | None,
    reason_tag: str,
    *,
    language: str = "ko",
) -> None:
    """최종 머지 실패를 알린다.
    Notify user of terminal merge failure.
    """
    chat_id = _resolve_retry_chat_id(row, cfg)
    if not chat_id or not settings.telegram_bot_token:
        return
    advice = get_advice(reason_tag, language)
    pr_url = f"https://github.com/{row.repo_full_name}/pull/{row.pr_number}"
    # HTML 태그는 키 값에 보존, 동적 값(repo/reason/advice/url)만 escape 후 kwargs 전달
    # HTML tags kept in key values; only dynamic values escaped before kwargs
    msg = (
        get_text("notifier.gate.retry_terminal_title", language) + "\n"
        + get_text(
            _RETRY_REPO_LINE_KEY, language,
            repo=escape(row.repo_full_name), pr=row.pr_number,
        ) + "\n"
        + get_text(
            "notifier.gate.retry_score_attempts", language,
            score=row.score, attempts=row.attempts_count,
        ) + "\n"
        + get_text(
            "notifier.gate.retry_terminal_reason", language,
            reason=escape(reason or reason_tag),
        ) + "\n"
        + get_text("notifier.gate.retry_advice_line", language, advice=escape(advice)) + "\n"
        + get_text("notifier.gate.retry_view_github", language, url=escape(pr_url))
    )
    try:
        await telegram_post_message(
            settings.telegram_bot_token, chat_id, {"text": msg, "parse_mode": "HTML"}
        )
    except HTTPX_SEND_ERRORS as exc:
        logger.warning("_notify_merge_terminal 전송 실패: %s", type(exc).__name__)


async def _create_failure_issue_safe(
    token: str,
    row: MergeRetryQueue,
    # C11: threshold 로그를 live cfg.merge_threshold 로 정합 (이제 사용됨)
    # C11: align the logged threshold with the live cfg.merge_threshold (now used)
    cfg: RepoConfigData,
    reason: str | None,
    reason_tag: str,
    *,
    language: str = "ko",
) -> None:
    """create_merge_failure_issue 를 안전하게 호출한다 (예외 격리).
    Safely call create_merge_failure_issue (exception-isolated).
    """
    advice = get_advice(reason_tag, language)
    try:
        await create_merge_failure_issue(
            github_token=token,
            repo_name=row.repo_full_name,
            pr_number=row.pr_number,
            score=row.score,
            threshold=cfg.merge_threshold,
            reason=reason or reason_tag,
            advice=advice,
            language=language,
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "create_merge_failure_issue 실패 (pr=%d): %s", row.pr_number, exc
        )
