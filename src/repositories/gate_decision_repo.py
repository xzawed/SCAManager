"""GateDecisionRepo — GateDecision ORM 쿼리·upsert 단일 출처."""
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.constants import HTTP_CLIENT_TIMEOUT
from src.models.gate_decision import GateDecision
from src.shared.time_utils import now_naive_utc, to_naive_utc

# 게시 상태 — 「결정했다」와 「리뷰가 붙었다」를 가른다 (#1504 R2).
PENDING_POST = "pending_post"
POSTED = "posted"

# 🔴 in-flight 클레임의 리스. `post_github_review` 는 head 조회 GET + 리뷰 POST 두 번
#    왕복하고 각각 `HTTP_CLIENT_TIMEOUT` 이다. 그 합에 여유를 준 값이고,
#    `merge_retry_repo` 의 300초를 베끼지 않는다 — 여기서는 **사람이 버튼 앞에서 기다린다**.
#    너무 길면 죽은 클레임이 버튼을 오래 막고, 너무 짧으면 정상 POST 중에 재클릭이 통과해
#    중복 리뷰가 난다.
# Two round trips at HTTP_CLIENT_TIMEOUT each, plus margin; deliberately shorter than the
# merge-retry sweep because a human is waiting on the button.
POST_LEASE_SECONDS = int(HTTP_CLIENT_TIMEOUT) * 6


def find_by_analysis_id(db: Session, analysis_id: int) -> GateDecision | None:
    """analysis_id 로 조회."""
    return db.query(GateDecision).filter_by(analysis_id=analysis_id).first()


def claim_decision(
    db: Session,
    analysis_id: int,
    decision: str,
    mode: str,
    decided_by: str | None = None,
) -> bool:
    """결정을 원자적으로 INSERT 한다 (first-writer-wins) — 이미 있으면 False 반환.
    Atomically INSERT the decision (first-writer-wins); return False if one already exists.

    UNIQUE(analysis_id) 제약으로 동시·멀티프로세스 리플레이 중 한 번만 INSERT 가 성공한다.
    리플레이 가드(handle_gate_callback)가 GitHub 리뷰·auto-merge 등 부수효과 전에 호출 —
    패자(이미 결정됨 또는 동시 INSERT 충돌)는 IntegrityError 를 흡수하고 부수효과를 skip 한다.
    upsert 와 달리 update 분기가 없어 결정 뒤집기를 원천 차단한다.
    The UNIQUE(analysis_id) constraint lets only one caller win under concurrent/multi-process
    replays; the replay guard calls this before side effects (GitHub review, auto-merge), so losers
    skip them. Unlike upsert there is no update branch — decisions cannot flip.
    (#780 save_new / #787 _ensure_repo 와 동일 race-safe 패턴 / same race-safe pattern.)

    ⚠️ **흡수 범위 주의**: `except IntegrityError` 는 UNIQUE 위반 외 FK(analyses.id ondelete)·
    NOT NULL 위반도 함께 False 로 흡수한다. 따라서 호출자(handle_gate_callback)는 호출 전에
    analysis 존재를 보장할 책임이 있다(현재 telegram.py 가 analysis 조회 후 호출). claim 호출 직전에
    DB write 를 추가하지 말 것 — IntegrityError 시 `db.rollback()` 이 세션 전체 트랜잭션을 되돌려
    그 write 까지 silent 폐기된다(현재 claim 전 read-only 라 무해).
    ⚠️ The bare `except IntegrityError` also absorbs FK / NOT NULL violations as False, so the caller
    must guarantee the analysis exists beforehand, and must NOT add a DB write right before this call
    (the rollback reverts the whole session transaction).
    """
    db.add(
        GateDecision(
            analysis_id=analysis_id,
            decision=decision,
            mode=mode,
            decided_by=decided_by,
            # 🔴 클레임은 「결정했다」이지 「게시했다」가 아니다 — 게시 확인은 `mark_posted`.
            state=PENDING_POST,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return False
    return True


def upsert(
    db: Session,
    analysis_id: int,
    decision: str,
    mode: str,
    decided_by: str | None = None,
) -> GateDecision:
    """GateDecision 을 upsert 한다 — 동일 analysis_id 있으면 UPDATE, 없으면 INSERT.

    재시도·반자동 재승인 시 중복 INSERT 를 방지한다.
    """
    record = find_by_analysis_id(db, analysis_id)
    if record:
        record.decision = decision
        record.mode = mode
        record.decided_by = decided_by
        record.state = POSTED
    else:
        record = GateDecision(
            analysis_id=analysis_id,
            decision=decision,
            mode=mode,
            decided_by=decided_by,
            # 🔴 자동 경로는 **게시 성공 뒤에** 부른다 — 재시도 대상이 아니다.
            #    `server_default` 에 기대지 않는다: ORM 속성을 안 채우면 INSERT 가 NULL 을
            #    보내고 새 재시도 갈래가 그 행을 「미게시」로 읽는다.
            state=POSTED,
        )
        db.add(record)
    db.commit()
    return record


def claim_post_attempt(
    db: Session,
    analysis_id: int,
    *,
    now: datetime | None = None,
    stale_after_seconds: int = POST_LEASE_SECONDS,
) -> GateDecision | None:
    """게시를 **배타적으로** 클레임한다 — 얻으면 그 행, 못 얻으면 None (#1504 R2).

    🔴 `state == PENDING_POST` 만 보고 POST 하면 안 된다. 두 클릭이 둘 다 그것을 보면
    둘 다 POST 해 **중복 리뷰**가 난다 — `claim_decision` 의 UNIQUE 가드가 막던 바로 그것이고,
    그 가드는 재시도 경로에서는 이미 통과된 뒤다.

    클레임 조건 (`merge_retry_repo::def claim_batch` 와 같은 형태):
      - `state == PENDING_POST`  — 게시된 결정은 리스가 아무리 낡아도 잡히지 않는다
      - `post_claimed_at IS NULL` 또는 `< now - stale_after_seconds` — 죽은 클레임 회수

    🔴 리스를 `decided_at` 으로 잡지 않는 이유는 모델 주석에 있다 — 만료 없는 HMAC 때문에
    늦은 클릭에서 CAS 가 무력해진다.

    🔴 **돌려주는 행의 `decision` 을 게시해야 한다** — 새 클릭의 결정이 아니다.
    HMAC 은 `gate:{analysis_id}` 만 서명하므로, 재시도가 새 결정을 게시하면
    `claim_decision` 이 막던 approve→reject **뒤집기**가 되살아난다.

    An exclusive begin-post claim: `pending_post` alone is not a lock, and the caller must post
    the CLAIMED decision, not the new click's, or the no-flip invariant is lost.
    """
    # 🔴 손수 tzinfo 를 벗기지 않는다 — 정본 헬퍼를 쓴다
    #    (`test_naive_utc_datetime_consistency.py` 가 우회를 잡는다).
    _now = to_naive_utc(now) if now is not None else now_naive_utc()
    cutoff = _now - timedelta(seconds=stale_after_seconds)
    row = (
        db.query(GateDecision)
        .filter(
            GateDecision.analysis_id == analysis_id,
            GateDecision.state == PENDING_POST,
            (GateDecision.post_claimed_at.is_(None))
            | (GateDecision.post_claimed_at < cutoff),
        )
        .first()
    )
    if row is None:
        return None
    row.post_claimed_at = _now
    db.commit()
    db.refresh(row)
    return row


def mark_posted(db: Session, analysis_id: int) -> None:
    """리뷰가 GitHub 에 붙었다 — 이후 클릭은 리플레이로 막힌다.

    🔴 `post_github_review` 가 돌아온 **직후**, auto-merge **전에** 부른다.
    그 경계가 `telegram.py` 의 `review_posted = True` 와 같은 자리다 — auto-merge 가 터져도
    리뷰는 이미 붙어 있으므로 재시도 대상이 아니다.
    """
    row = find_by_analysis_id(db, analysis_id)
    if row is None:
        return
    row.state = POSTED
    row.post_claimed_at = None
    db.commit()


def release_post_claim(db: Session, analysis_id: int) -> None:
    """알려진 실패에서 in-flight 클레임을 즉시 푼다 — 사람을 리스만큼 기다리게 하지 않는다.

    🔴 `state` 는 건드리지 않는다. 이미 `POSTED` 인 행에 불려도 되살아나지 않아야 한다
    (게시 성공 뒤 auto-merge 가 터진 경로가 이 함수를 지날 수 있다).
    Clears only the in-flight lease; a posted decision must never be resurrected.
    """
    row = find_by_analysis_id(db, analysis_id)
    if row is None or row.state == POSTED:
        return
    row.post_claimed_at = None
    db.commit()
