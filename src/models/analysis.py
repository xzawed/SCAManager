"""Analysis ORM 모델 — 분석 이력(정적 분석 + AI 리뷰 점수) 저장."""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, Integer, String, JSON, DateTime, ForeignKey, UniqueConstraint, Index, text,
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
        # 0032: 월별 토큰 합산 쿼리용 부분 인덱스 (input_tokens IS NOT NULL).
        # ORM↔alembic 정합 (#18 drift ③) — postgresql/sqlite 양 방언 부분 인덱스 선언.
        # 0032: partial index for monthly token aggregation; declared for ORM↔alembic parity.
        Index(
            "ix_analyses_repo_id_created_at_tokens",
            "repo_id", "created_at",
            postgresql_where=text("input_tokens IS NOT NULL"),
            sqlite_where=text("input_tokens IS NOT NULL"),
        ),
        # 0046: 집계는 «점수가 있고 신뢰 가능한» 행만 본다 — 부분 인덱스가 Index Only Scan 을
        # 만든다(실측 0.45 ms · 버퍼 6; 없으면 2.17 ms · 버퍼 1,145). 운영 기준 29% 만 덮는다.
        Index(
            "ix_analyses_reliable_scores",
            "repo_id", "score",
            postgresql_where=text("score IS NOT NULL AND score_unreliable IS NOT TRUE"),
            sqlite_where=text("score IS NOT NULL AND score_unreliable IS NOT TRUE"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    # repo_id FK — ondelete=CASCADE: repositories 삭제 시 analyses(+child 4종 CASCADE) 동반 삭제 (#14)
    # repo_id FK — CASCADE: deleting a repository cascades to analyses (+ its 4 CASCADE children).
    repo_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
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

    # 리뷰에 사용된 Claude 모델 — 비용 계산용 (Alembic 0032)
    # Claude model used for this review — for cost calculation (Alembic 0032)
    review_model = Column(String(50), nullable=True)
    # Anthropic API 실제 토큰 사용량 — 비용 계산용 (Alembic 0032)
    # Actual Anthropic API token usage — for cost calculation (Alembic 0032)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)

    # 🔴 `score_is_unreliable(result)` 의 **비정규화 캐시** (Alembic 0046).
    #
    # 집계(평균·추세)는 이 판정으로 행을 걸러내는데, 판정 근거가 `result` JSON 안에 있어
    # 그 전량을 읽어야 했다. 실측(로컬 PG17, 운영 동형 5,164행 · 33 MB):
    #     json 전체 blob 로드          16.2 ms · 5,164행 · 33 MB 전송
    #     json 5경로 `->` 추출        422.5 ms  ← `json` 은 텍스트라 접근마다 재파싱
    #     jsonb 5경로 `->`             74.7 ms  (테이블 재작성 필요, 여전히 5,164행)
    #     이 컬럼 + 부분인덱스           0.45 ms · **4행**
    #
    # 🔴 이것은 **캐시**지 정의가 아니다. 정의는 `scorer/reliability.score_is_unreliable`
    #    하나뿐이고, 이 컬럼이 그것과 어긋나면 평균이 조용히 틀린다(예외도 red 도 없이).
    #    판정 함수 본문이 바뀌면 백필 리비전을 강제하는 가드가 CI 에 있다
    #    (`tests/unit/scorer/test_reliability_cache_contract.py`).
    #
    # Denormalized cache of `score_is_unreliable(result)`: aggregates filtered on a predicate whose
    # inputs live inside the JSON blob, forcing a full read. This is a cache, not the definition;
    # a CI guard forces a backfill revision whenever the predicate body changes.
    # 🔴 기본값이 **true(신뢰 불가)** 다 — fail-closed (Grok claim-review `01a02f70` Q3).
    #    이 기본값이 적용되는 경우는 「쓰기가 이 컬럼을 빠뜨렸을 때」뿐이다:
    #      · 새 쓰기 경로가 대입을 잊음  · 배포 교체 중 옛 바이너리의 insert
    #      · 미래의 bulk/raw SQL 경로
    #    false 로 두면 그 행이 **검증된 점수로 평균에 들어간다** — R46 Axis B 의 재현이다.
    #    운영 실측 신뢰불가 비율 70.8% 를 감안하면 「모르면 신뢰 가능」은 나쁜 사전확률이다.
    #    true 면 모르는 행은 평균에서 빠진다 — 판정 자체가 fail-closed 인 것과 방향이 같다.
    #    Unknown rows must not enter verified averages; the default is the backstop for
    #    forgotten writes, so it points the same way the predicate does.
    score_unreliable = Column(
        Boolean, nullable=False, server_default=text("true"),
    )

    repository = relationship("Repository", back_populates="analyses")
