"""AnalysisAttemptRepo — 분석 시작 흔적(AnalysisAttempt) 쿼리 단일 출처.

AnalysisAttemptRepo — single source for AnalysisAttempt queries.

용도: 파이프라인 소실 탐지. 배경·설계 이유는 `src/models/analysis_attempt.py` docstring 참조.
Purpose: pipeline loss detection. See `src/models/analysis_attempt.py` for background/design.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.models.analysis_attempt import AnalysisAttempt


def _now_naive() -> datetime:
    """현재 UTC 시각 — naive datetime (ORM 규약, tzinfo=None).
    Current UTC time as a naive datetime (ORM convention, tzinfo=None).

    started_at 은 naive DateTime 컬럼이라 aware 값과 비교하면 PG(TIMESTAMP WITHOUT TIME ZONE)
    에서 의미가 어긋난다 (SQLite 는 tzinfo 를 조용히 버려 통과 — 테스트가 못 잡는 영역).
    started_at is a naive DateTime column; comparing it against an aware value diverges on PG
    (TIMESTAMP WITHOUT TIME ZONE), while SQLite silently drops tzinfo and passes — untestable drift.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def begin_attempt(
    db: Session,
    *,
    repo_id: int,
    commit_sha: str,
    pr_number: int | None = None,
    event: str | None = None,
) -> bool:
    """분석 시작 흔적을 남긴다 — 이미 있으면 False (first-writer-wins).

    Record that an analysis started — returns False if one already exists (first-writer-wins).

    🔴 이 함수는 **dedup 게이트가 아니다.** False 를 반환해도 호출자는 파이프라인을 계속
    진행해야 한다 — 중복 분석 차단은 `Analysis.find_by_sha`(_ensure_repo/_save_and_gate)의
    책임이며, 여기서 조기 return 하면 그 first-writer-wins 불변식(#794·#780)과 이중으로
    얽혀 동작이 갈라진다.
    🔴 This is NOT a dedup gate. Callers must proceed even when it returns False — duplicate
    analysis is `Analysis.find_by_sha`'s responsibility (_ensure_repo/_save_and_gate); short-
    circuiting here would entangle and diverge from those first-writer-wins invariants.
    """
    db.add(AnalysisAttempt(
        repo_id=repo_id,
        commit_sha=commit_sha,
        pr_number=pr_number,
        event=event,
    ))
    try:
        db.commit()
        return True
    except IntegrityError:
        # 동시 webhook 이 같은 SHA 로 먼저 시작 — 정상 경로다. 예외를 전파하면 워커가
        # 죽으므로 rollback 후 False. 세션은 이후 호출자가 계속 쓸 수 있어야 한다.
        # A concurrent webhook started the same SHA first — a normal path. Propagating would
        # abort the worker, so roll back and return False; the session stays usable afterwards.
        db.rollback()
        return False


def finish_attempt(db: Session, *, repo_id: int, commit_sha: str) -> None:
    """분석 흔적을 지운다 — 정상 종료 신호. 행이 없으면 no-op (멱등).

    Delete the attempt breadcrumb — the normal-completion signal. No-op if absent (idempotent).

    🔴 실패·크래시 경로에서는 **호출하지 말 것.** 남은 행이 곧 소실 증거다.
    🔴 Never call this on a failure/crash path — the surviving row is the evidence of loss.
    """
    db.query(AnalysisAttempt).filter_by(
        repo_id=repo_id, commit_sha=commit_sha,
    ).delete(synchronize_session=False)
    db.commit()


def find_orphaned(db: Session, *, older_than_minutes: int) -> list[AnalysisAttempt]:
    """소실 후보를 반환한다 — `older_than_minutes` 보다 오래 남아 있는 흔적.

    Return loss candidates — breadcrumbs older than `older_than_minutes`.

    정상 분석은 수 분 내 `finish_attempt` 로 지워지므로, 임계를 넘겨 남은 행은
    SIGTERM/OOM/크래시로 증발한 분석이다. 오름차순(오래된 것 먼저) 정렬.
    A healthy analysis is cleared within minutes, so a row past the threshold means the analysis
    vanished to a SIGTERM/OOM/crash. Ordered oldest-first.
    """
    cutoff = _now_naive() - timedelta(minutes=older_than_minutes)
    return (
        db.query(AnalysisAttempt)
        .filter(AnalysisAttempt.started_at < cutoff)
        .order_by(AnalysisAttempt.started_at.asc())
        .all()
    )
