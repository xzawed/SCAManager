"""GateDecisionRepo — GateDecision ORM 쿼리·upsert 단일 출처."""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.gate_decision import GateDecision


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
    upsert(save_gate_decision)와 달리 update 분기가 없어 결정 뒤집기를 원천 차단한다.
    The UNIQUE(analysis_id) constraint lets only one caller win under concurrent/multi-process
    replays; the replay guard calls this before side effects (GitHub review, auto-merge), so losers
    skip them. Unlike the upsert (save_gate_decision) there is no update branch — decisions cannot flip.
    (#780 save_new / #787 _ensure_repo 와 동일 race-safe 패턴 / same race-safe pattern.)
    """
    db.add(
        GateDecision(
            analysis_id=analysis_id,
            decision=decision,
            mode=mode,
            decided_by=decided_by,
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
    else:
        record = GateDecision(
            analysis_id=analysis_id,
            decision=decision,
            mode=mode,
            decided_by=decided_by,
        )
        db.add(record)
    db.commit()
    return record
