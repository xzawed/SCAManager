"""merge_retry_repo — MergeRetryQueue 기본 CRUD + claim 의미론 단일 출처 (Phase 12 T1+T6).

기본 CRUD 4개 + claim 의미론 8개 함수 노출:
  - get()                   — 기본 키 조회
  - list_pending()          — 처리 대상 pending 행 목록 (next_retry_at <= now)
  - get_by_sha()            — (repo_full_name, commit_sha) 로 비종료 행 조회
  - delete_all_for_repo()   — repo 전체 행 하드 삭제 (cascade 정리용)
  [T6 claim 의미론]
  - enqueue_or_bump()       — 신규 추가 또는 기존 pending 행 next_retry_at 갱신
  - claim_batch()           — 처리 가능한 행들을 원자적으로 클레임
  - release_claim()         — 클레임 해제 — 재시도 대기 상태로 복귀
  - mark_succeeded()        — status='succeeded' 마킹
  - mark_terminal()         — status='failed_terminal' 마킹
  - mark_expired()          — status='expired' 마킹
  - mark_abandoned()        — status='abandoned' 마킹
  - abandon_stale_for_pr()  — force-push 감지 시 오래된 SHA pending 행 포기 처리
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from src.models.merge_retry import MergeRetryQueue

# 비종료 상태 — 이 상태의 행만 get_by_sha 에서 반환한다
# Non-terminal statuses — get_by_sha only returns rows with these statuses.
_NON_TERMINAL_STATUSES = {"pending"}


def get(db: Session, row_id: int) -> MergeRetryQueue | None:
    """기본 키로 MergeRetryQueue 행을 조회한다.
    Fetch a MergeRetryQueue row by primary key.
    """
    return db.query(MergeRetryQueue).filter(MergeRetryQueue.id == row_id).first()


def list_pending(
    db: Session,
    *,
    now: datetime,
    limit: int = 50,
) -> list[MergeRetryQueue]:
    """재시도 대상 pending 행 목록 — status='pending' AND next_retry_at <= now.

    next_retry_at ASC 정렬 — 가장 오래된 예정 행 우선 처리.
    Returns pending rows due for retry, ordered by next_retry_at ASC (oldest first).
    """
    return (
        db.query(MergeRetryQueue)
        .filter(
            MergeRetryQueue.status == "pending",
            MergeRetryQueue.next_retry_at <= now,
        )
        .order_by(MergeRetryQueue.next_retry_at.asc())
        .limit(limit)
        .all()
    )


def get_by_sha(
    db: Session,
    *,
    repo_full_name: str,
    commit_sha: str,
) -> MergeRetryQueue | None:
    """(repo_full_name, commit_sha) 로 비종료 상태 행 첫 번째를 조회한다.

    비종료: status = 'pending' (T6 이후 확장 가능).
    Fetch the first non-terminal row for (repo_full_name, commit_sha).
    Non-terminal: status = 'pending' (extendable in T6+).
    """
    return (
        db.query(MergeRetryQueue)
        .filter(
            MergeRetryQueue.repo_full_name == repo_full_name,
            MergeRetryQueue.commit_sha == commit_sha,
            MergeRetryQueue.status.in_(_NON_TERMINAL_STATUSES),
        )
        .first()
    )


def find_pending_by_sha(
    db: Session,
    *,
    repo_full_name: str,
    commit_sha: str,
) -> list[MergeRetryQueue]:
    """(repo_full_name, commit_sha) 로 pending 상태 행 전체를 조회한다.

    check_suite.completed 트리거 시 재시도 대상 행 목록 조회에 사용.
    Used to look up all retry-eligible rows when check_suite.completed arrives.
    """
    return (
        db.query(MergeRetryQueue)
        .filter(
            MergeRetryQueue.repo_full_name == repo_full_name,
            MergeRetryQueue.commit_sha == commit_sha,
            MergeRetryQueue.status == "pending",
        )
        .all()
    )


def delete_all_for_repo(
    db: Session,
    *,
    repo_full_name: str,
) -> int:
    """해당 repo 의 모든 MergeRetryQueue 행을 하드 삭제하고 삭제 수를 반환한다.

    리포 삭제 cascade 정리용 — Analysis ON DELETE CASCADE 와 함께 고아 레코드 방지.
    Hard-deletes all rows for the given repo and returns the count deleted.
    Used for repo cascade cleanup — complements Analysis ON DELETE CASCADE.
    """
    count = (
        db.query(MergeRetryQueue)
        .filter(MergeRetryQueue.repo_full_name == repo_full_name)
        .delete(synchronize_session=False)
    )
    db.commit()
    return count


# ---------------------------------------------------------------------------
# T6: Claim semantics
# T6: 클레임 의미론
# ---------------------------------------------------------------------------


def _now_naive() -> datetime:
    """현재 UTC 시각 — naive datetime (ORM 규약, tzinfo=None).
    Current UTC time as a naive datetime (ORM convention, tzinfo=None).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class EnqueueResult:
    """enqueue_or_bump 결과 — 신규 생성 여부와 큐 행 반환.
    enqueue_or_bump result — whether it was newly created and the queue row.
    """

    # 큐 행 (신규 생성 또는 기존 업데이트)
    # The queue row (newly created or existing updated).
    row: MergeRetryQueue

    # True 이면 신규 생성, False 이면 기존 행 업데이트(bump)
    # True if newly created; False if existing row was bumped.
    is_first_deferral: bool


def enqueue_or_bump(  # pylint: disable=too-many-arguments
    db: Session,
    *,
    repo_full_name: str,
    pr_number: int,
    analysis_id: int,
    commit_sha: str,
    score: int,
    threshold_at_enqueue: int,
    notify_chat_id: str | None = None,
    max_attempts: int = 30,
    now: datetime | None = None,
    initial_next_retry_seconds: int = 60,
) -> EnqueueResult:
    """재시도 큐에 항목을 추가하거나 기존 항목의 next_retry_at 을 갱신한다.
    Add an item to the retry queue or update next_retry_at on an existing one.

    조회 기준: repo_full_name + pr_number + commit_sha + status='pending'.
    Lookup key: repo_full_name + pr_number + commit_sha + status='pending'.

    - 행 없음: INSERT (status='pending', attempts_count=0), is_first_deferral=True
    - 행 있음: next_retry_at 갱신(bump), attempts_count 유지, is_first_deferral=False
    - No row:  INSERT (status='pending', attempts_count=0), is_first_deferral=True
    - Exists:  Update next_retry_at (bump), preserve attempts_count, is_first_deferral=False
    """
    _now = now or _now_naive()
    next_retry = _now + timedelta(seconds=initial_next_retry_seconds)

    # 기존 pending 행 조회
    # Look up existing pending row.
    existing = (
        db.query(MergeRetryQueue)
        .filter(
            MergeRetryQueue.status == "pending",
            MergeRetryQueue.repo_full_name == repo_full_name,
            MergeRetryQueue.pr_number == pr_number,
            MergeRetryQueue.commit_sha == commit_sha,
        )
        .first()
    )

    if existing is not None:
        # 기존 행 bump — next_retry_at 갱신, attempts_count 유지
        # Bump existing row — update next_retry_at, preserve attempts_count.
        existing.next_retry_at = next_retry
        existing.updated_at = _now
        db.commit()
        db.refresh(existing)
        return EnqueueResult(row=existing, is_first_deferral=False)

    # 신규 행 생성
    # Create new row.
    new_row = MergeRetryQueue(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        analysis_id=analysis_id,
        commit_sha=commit_sha,
        score=score,
        threshold_at_enqueue=threshold_at_enqueue,
        status="pending",
        attempts_count=0,
        max_attempts=max_attempts,
        next_retry_at=next_retry,
        notify_chat_id=notify_chat_id,
    )
    db.add(new_row)
    db.commit()
    db.refresh(new_row)
    return EnqueueResult(row=new_row, is_first_deferral=True)


def claim_batch(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = 50,
    stale_after_seconds: int = 300,
    only_ids: list[int] | None = None,
) -> list[MergeRetryQueue]:
    """처리 가능한 행들을 원자적으로 클레임한다 (SELECT + UPDATE).
    Atomically claim processable rows (SELECT then UPDATE).

    클레임 대상 조건:
    Claimable condition:
      - status = 'pending'
      - next_retry_at <= now (재시도 예정 시각 도달)
      - next_retry_at <= now (retry due time reached)
      - claimed_at IS NULL  OR  claimed_at < now - stale_after_seconds (stale 클레임 재획득)
      - claimed_at IS NULL  OR  claimed_at < now - stale_after_seconds (reclaim stale)

    클레임 처리: claimed_at=now, claim_token=uuid, attempts_count+=1, last_attempt_at=now
    Claim action: claimed_at=now, claim_token=uuid, attempts_count+=1, last_attempt_at=now

    SQLite 호환: StaticPool 단일 연결 환경에서 SELECT+UPDATE 가 사실상 원자적.
    SQLite compatibility: SELECT+UPDATE is effectively atomic under StaticPool (single connection).
    """
    _now = now or _now_naive()
    stale_cutoff = _now - timedelta(seconds=stale_after_seconds)

    # 클레임 가능 행 조회
    # Query claimable rows.
    query = db.query(MergeRetryQueue).filter(
        MergeRetryQueue.status == "pending",
        MergeRetryQueue.next_retry_at <= _now,
        # claimed_at IS NULL 또는 stale 기준 초과
        # claimed_at IS NULL or exceeds stale threshold.
        (
            MergeRetryQueue.claimed_at.is_(None)
            | (MergeRetryQueue.claimed_at < stale_cutoff)
        ),
    )
    if only_ids:
        query = query.filter(MergeRetryQueue.id.in_(only_ids))

    rows = query.order_by(MergeRetryQueue.next_retry_at.asc()).limit(limit).all()

    if not rows:
        return []

    # 배치 내 동일 토큰 사용 (단일 UUID) — 허용 가능한 설계
    # Same token for entire batch (single UUID) — acceptable for this use case.
    tok = str(uuid.uuid4())[:36]
    for row in rows:
        row.claimed_at = _now
        row.claim_token = tok
        row.attempts_count += 1
        row.last_attempt_at = _now
        row.updated_at = _now
    db.commit()

    # 갱신된 상태 반영을 위해 refresh
    # Refresh to reflect updated state.
    for row in rows:
        db.refresh(row)

    return rows


def release_claim(
    db: Session,
    row_id: int,
    *,
    next_retry_at: datetime,
    last_failure_reason: str | None = None,
    last_detail_message: str | None = None,
    now: datetime | None = None,
) -> bool:
    """클레임 해제 — pending 재시도 대기 상태로 복귀.
    Release a claim — return row to pending state for retry.

    claimed_at=None, claim_token=None, next_retry_at 갱신.
    Sets claimed_at=None, claim_token=None, updates next_retry_at.
    행 없으면 False, 있으면 True 반환.
    Returns False if row not found, True if found.
    """
    _now = now or _now_naive()

    row = db.query(MergeRetryQueue).filter(MergeRetryQueue.id == row_id).first()
    if row is None:
        return False

    row.claimed_at = None
    row.claim_token = None
    row.next_retry_at = next_retry_at
    if last_failure_reason is not None:
        row.last_failure_reason = last_failure_reason
    if last_detail_message is not None:
        row.last_detail_message = last_detail_message
    row.updated_at = _now
    db.commit()
    return True


def _mark_status(
    db: Session,
    row_id: int,
    *,
    status: str,
    reason: str | None,
    now: datetime,
) -> bool:
    """상태 마킹 공통 헬퍼 — claimed_at/claim_token 초기화 포함.
    Common helper for status marking — also clears claimed_at/claim_token.
    """
    row = db.query(MergeRetryQueue).filter(MergeRetryQueue.id == row_id).first()
    if row is None:
        return False
    row.status = status
    if reason is not None:
        row.last_failure_reason = reason
    row.claimed_at = None
    row.claim_token = None
    row.updated_at = now
    db.commit()
    return True


def mark_succeeded(
    db: Session,
    row_id: int,
    *,
    reason: str | None = None,
    now: datetime | None = None,
) -> bool:
    """status='succeeded' 마킹 — 재시도 성공 시 호출.
    Mark status as 'succeeded' — called on successful merge retry.
    행 없으면 False 반환.
    Returns False if row not found.
    """
    _now = now or _now_naive()
    return _mark_status(db, row_id, status="succeeded", reason=reason, now=_now)


def mark_terminal(
    db: Session,
    row_id: int,
    *,
    reason: str,
    now: datetime | None = None,
) -> bool:
    """status='failed_terminal' 마킹 — 재시도 불가 오류 (권한 없음 등).
    Mark status as 'failed_terminal' — non-retryable error (e.g. permission denied).
    행 없으면 False 반환.
    Returns False if row not found.
    """
    _now = now or _now_naive()
    return _mark_status(db, row_id, status="failed_terminal", reason=reason, now=_now)


def mark_expired(
    db: Session,
    row_id: int,
    *,
    reason: str | None = None,
    now: datetime | None = None,
) -> bool:
    """status='expired' 마킹 — SHA 가 PR head 가 아닐 때 (force-push 등).
    Mark status as 'expired' — when SHA is no longer PR head (e.g. force-push).
    행 없으면 False 반환.
    Returns False if row not found.
    """
    _now = now or _now_naive()
    return _mark_status(db, row_id, status="expired", reason=reason, now=_now)


def mark_abandoned(
    db: Session,
    row_id: int,
    *,
    reason: str,
    now: datetime | None = None,
) -> bool:
    """status='abandoned' 마킹 — max_attempts 초과 등 포기 시.
    Mark status as 'abandoned' — when max_attempts is exceeded or caller gives up.
    행 없으면 False 반환.
    Returns False if row not found.
    """
    _now = now or _now_naive()
    return _mark_status(db, row_id, status="abandoned", reason=reason, now=_now)


def abandon_stale_for_pr(
    db: Session,
    *,
    repo_full_name: str,
    pr_number: int,
    current_sha: str,
    reason: str = "sha_drift",
    now: datetime | None = None,
) -> int:
    """force-push 감지 시 이전 SHA 의 pending 행들을 abandoned 로 마킹한다.
    Mark old-SHA pending rows as abandoned when force-push is detected.

    (repo_full_name, pr_number) 기준으로 commit_sha != current_sha 인 pending 행 모두 처리.
    Updates all pending rows for (repo, pr_number) where commit_sha != current_sha.
    포기 처리된 행 수를 반환한다.
    Returns count of rows abandoned.
    """
    _now = now or _now_naive()

    # 이전 SHA 의 pending 행 조회
    # Query pending rows with old SHA.
    stale_rows = (
        db.query(MergeRetryQueue)
        .filter(
            MergeRetryQueue.repo_full_name == repo_full_name,
            MergeRetryQueue.pr_number == pr_number,
            MergeRetryQueue.status == "pending",
            MergeRetryQueue.commit_sha != current_sha,
        )
        .all()
    )

    for row in stale_rows:
        row.status = "abandoned"
        row.last_failure_reason = reason
        row.claimed_at = None
        row.claim_token = None
        row.updated_at = _now

    if stale_rows:
        db.commit()

    return len(stale_rows)
