"""MergeAttempt ORM — Phase F.1 auto-merge 시도 이력 관측 테이블.

모든 auto-merge 시도(성공·실패 모두)를 1:N 으로 Analysis 에 연결해 기록한다.
재시도·멱등 이벤트로 여러 번 시도되는 경우에도 각 시도를 별도 row 로 보존 —
upsert 가 아닌 순수 append-only 이력.

**설계 의도**:
  - `failure_reason` 은 `src/gate/merge_reasons.py` 의 정규 태그 (branch_protection_blocked,
    dirty_conflict, unstable_ci, permission_denied 등) — 집계 쿼리 안정성 보장.
  - `detail_message` 는 GitHub 원문 메시지 포함 full reason — 운영 디버깅용.
  - `score`/`threshold` 는 시도 시점 스냅샷 — 기준 변경 후에도 당시 맥락 재현 가능.
  - `ondelete=CASCADE`: 리포 삭제로 Analysis 가 사라지면 관측 이력도 동반 삭제 —
    Phase F.4 대시보드는 현존 Analysis 기준 집계이므로 고아 레코드 방지 우선.

**집계 쿼리 진입점**: `src/repositories/merge_attempt_repo.py`.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from src.database import Base


# pylint: disable=too-few-public-methods
class MergeAttempt(Base):
    """auto-merge 시도 1회 기록 — 성공·실패 모두 저장."""

    __tablename__ = "merge_attempts"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    repo_name = Column(String, nullable=False, index=True)
    pr_number = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False)
    threshold = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String, nullable=True)
    detail_message = Column(String, nullable=True)
    attempted_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
