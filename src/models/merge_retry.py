"""MergeRetryQueue ORM — Phase 12 CI-aware auto-merge 재시도 큐 테이블.

CI 가 아직 실행 중이어서 merge 가 실패한 경우, 큐에 넣고 재시도한다.
When a merge fails because CI is still running, enqueue and retry.

상태 전이 (status transitions):
  pending → succeeded        — 재시도 성공
  pending → failed_terminal  — 재시도 가능하지 않은 오류 (권한 없음, branch protection 등)
  pending → abandoned        — max_attempts 초과
  pending → expired          — 커밋 SHA 가 더 이상 PR head 가 아님
"""
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text

from src.database import Base


# pylint: disable=too-few-public-methods
class MergeRetryQueue(Base):
    """CI-aware auto-merge 재시도 큐 행 — 상태: pending/succeeded/failed_terminal/abandoned/expired.
    Retry queue row — states: pending/succeeded/failed_terminal/abandoned/expired.
    """

    __tablename__ = "merge_retry_queue"

    # 기본 키
    # Primary key.
    id = Column(Integer, primary_key=True, index=True)

    # 리포 식별자 — GitHub full_name 형식 (owner/repo)
    # Repository identifier — GitHub full_name format (owner/repo).
    repo_full_name = Column(String, nullable=False)

    # PR 번호
    # Pull request number.
    pr_number = Column(Integer, nullable=False)

    # 분석 ID — 연관 Analysis 레코드 (삭제 시 CASCADE)
    # Analysis ID — linked Analysis record (CASCADE on delete).
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
    )

    # 큐에 넣은 시점의 커밋 SHA (40자)
    # Commit SHA at enqueue time (40 chars).
    commit_sha = Column(String(40), nullable=False)

    # 큐에 넣은 시점의 점수 스냅샷
    # Score snapshot at enqueue time.
    score = Column(Integer, nullable=False)

    # 큐에 넣은 시점의 merge threshold 스냅샷
    # Merge threshold snapshot at enqueue time.
    threshold_at_enqueue = Column(Integer, nullable=False)

    # 현재 상태 — 기본값 'pending'
    # Current status — default 'pending'.
    status = Column(String, nullable=False, default="pending", server_default="pending")

    # 총 시도 횟수 — 성공/실패 모두 카운트
    # Total attempt count — includes successes and failures.
    attempts_count = Column(Integer, nullable=False, default=0, server_default="0")

    # 최대 허용 시도 횟수 — 초과 시 abandoned 로 전환
    # Maximum allowed attempts — transitions to abandoned when exceeded.
    max_attempts = Column(Integer, nullable=False, default=30, server_default="30")

    # 다음 재시도 예정 시각
    # Scheduled next retry time.
    next_retry_at = Column(DateTime, nullable=False)

    # 마지막 시도 시각 (최초 시도 전 NULL)
    # Last attempt time (NULL before first attempt).
    last_attempt_at = Column(DateTime, nullable=True)

    # Worker 가 행을 잠근 시각 — 분산 중복 실행 방지 (T6 claim 의미론)
    # Time when a worker claimed this row — prevents duplicate execution (T6 claim semantics).
    claimed_at = Column(DateTime, nullable=True)

    # Worker claim 토큰 — UUID4 형식 (T6 claim 의미론)
    # Worker claim token — UUID4 format (T6 claim semantics).
    claim_token = Column(String(36), nullable=True)

    # 마지막 실패 이유 정규 태그 (merge_reasons.py 참조)
    # Last failure reason tag (see merge_reasons.py).
    last_failure_reason = Column(String, nullable=True)

    # 마지막 실패 상세 메시지 (GitHub 원문 포함)
    # Last failure detail message (includes GitHub raw message).
    last_detail_message = Column(Text, nullable=True)

    # 알림 수신 Telegram chat_id (enqueue 시점 스냅샷)
    # Telegram chat_id for notifications (snapshot at enqueue time).
    notify_chat_id = Column(String, nullable=True)

    # 레코드 생성 시각
    # Record creation time.
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # 레코드 마지막 갱신 시각
    # Record last update time.
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # sweep 인덱스 — (status, next_retry_at) 조합으로 미처리 행 스캔 최적화
        # Sweep index — optimizes scanning for unprocessed rows by (status, next_retry_at).
        Index("ix_merge_retry_queue_sweep", "status", "next_retry_at"),
        # SHA 조회 인덱스 — 특정 커밋의 큐 상태 빠른 조회
        # SHA lookup index — fast lookup of queue status for a specific commit.
        Index("ix_merge_retry_queue_sha_lookup", "repo_full_name", "commit_sha", "status"),
    )
