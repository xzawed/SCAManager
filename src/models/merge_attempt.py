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
    # Phase 3 PR-B1 — Tier 3 PR-A 후속: 머지 라이프사이클 추적
    # state 의미:
    #   - "legacy" — 0022 마이그레이션 이전 모든 행 (backfill 기본값)
    #   - "enabled_pending_merge" — native enablePullRequestAutoMerge 성공,
    #     GitHub 측 비동기 머지 대기 (실제 머지는 미발생)
    #   - "actually_merged" — pull_request.closed merged=true webhook 수신 →
    #     state 전이됨 (enabled_pending_merge 행만 갱신)
    #   - "disabled_externally" — pull_request.auto_merge_disabled webhook
    #     (force-push, check 실패, 사용자 수동 해제 등)
    #   - "direct_merged" — REST merge_pr() 즉시 성공 (폴백 또는 legacy 경로)
    #
    # Phase 3 PR-B1 — Tier 3 PR-A follow-up: track auto-merge lifecycle.
    # state semantics:
    #   - "legacy"               — pre-0022 rows (backfill default)
    #   - "enabled_pending_merge" — native enable success, GitHub will merge async
    #   - "actually_merged"      — pull_request.closed merged=true webhook
    #   - "disabled_externally"  — pull_request.auto_merge_disabled webhook
    #   - "direct_merged"        — REST merge_pr() immediate success (fallback/legacy)
    state = Column(String, nullable=False, server_default="legacy")
    enabled_at = Column(DateTime, nullable=True)
    merged_at = Column(DateTime, nullable=True)
    disabled_at = Column(DateTime, nullable=True)
