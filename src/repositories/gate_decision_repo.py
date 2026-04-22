"""GateDecisionRepo — GateDecision ORM 쿼리·upsert 단일 출처."""
from sqlalchemy.orm import Session

from src.models.gate_decision import GateDecision


def find_by_analysis_id(db: Session, analysis_id: int) -> GateDecision | None:
    """analysis_id 로 조회."""
    return db.query(GateDecision).filter_by(analysis_id=analysis_id).first()


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
