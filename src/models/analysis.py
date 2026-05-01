"""Analysis ORM 모델 — 분석 이력(정적 분석 + AI 리뷰 점수) 저장."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, JSON, DateTime, ForeignKey, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship
from src.database import Base


# pylint: disable=too-few-public-methods
class Analysis(Base):
    """Push/PR 분석 이력 테이블 — commit_sha별 점수·등급·AI 리뷰 결과 저장."""

    __tablename__ = "analyses"
    # Phase H PR-4A — 복합 인덱스 2종:
    #   (repo_id, created_at) — `WHERE repo_id=X ORDER BY created_at DESC LIMIT N`
    #     analytics_service.weekly_summary / moving_average / repo_detail 차트
    #   (repo_id, author_login) — leaderboard / author_trend 집계
    # 단일 컬럼 created_at/author_login 인덱스는 다른 쿼리(전역 추세 등) 용으로 유지.
    # Phase H PR-4A — composite indexes for repo-scoped sort/group queries.
    __table_args__ = (
        UniqueConstraint("repo_id", "commit_sha", name="uq_analyses_repo_sha"),
        Index("ix_analyses_repo_id_created_at", "repo_id", "created_at"),
        Index("ix_analyses_repo_id_author_login", "repo_id", "author_login"),
    )

    id = Column(Integer, primary_key=True, index=True)
    repo_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    commit_sha = Column(String, nullable=False, index=True)
    commit_message = Column(String, nullable=True)
    pr_number = Column(Integer, nullable=True)
    score = Column(Integer, nullable=True)
    grade = Column(String(1), nullable=True)
    result = Column(JSON, nullable=True)
    # 커밋 작성자 GitHub 로그인 — 신규 레코드만 채움 (기존 NULL 허용)
    # GitHub login of the commit author — populated for new records only (existing rows NULL).
    author_login = Column(String, nullable=True, index=True)
    # Phase 2 — created_at 인덱스 (Alembic 0021): 추세 차트·analytics_service 의
    # `ORDER BY created_at DESC LIMIT N` 쿼리에서 풀스캔 → 인덱스 스캔 전환.
    # 1만 row 시점부터 P95 latency ~180ms → <50ms 개선 (14-에이전트 감사 R3-B).
    # Phase 2 — created_at index (Alembic 0021): converts trend/analytics queries
    # from full scan to index scan; P95 ~180ms → <50ms past 10K rows.
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    repository = relationship("Repository", back_populates="analyses")
