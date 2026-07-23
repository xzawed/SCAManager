"""AnalysisAttempt ORM 모델 — 진행 중인 분석의 흔적(소실 탐지용).

AnalysisAttempt ORM model — a breadcrumb for in-flight analyses (loss detection).

🔴 존재 이유: 분석 파이프라인은 in-process BackgroundTask 로 돌고 내구 큐가 없다.
webhook 핸들러가 GitHub 에 200 을 **선반환**한 뒤 파일 수집 + Claude 리뷰(수 분)를 하는데,
유일한 내구 기록인 `Analysis` 행은 그 **모든 작업이 끝난 뒤** 저장된다. 그 창에서
SIGTERM(Railway 재배포)·OOM·크래시가 나면 Analysis 행도, 재시도도, GitHub 재전송도 없어
분석이 **조용히 증발**하고 "아직 분석 안 됨"과 영영 구별되지 않는다.

이 테이블은 소실을 **막지 않는다 — 탐지 가능하게 만든다.** 비싼 작업 *전에* 행을 남기고
정상 종료 시 지운다. 따라서 **남아 있는 오래된 행 = 소실된 분석**이다.

🔴 Why this exists: the analysis pipeline runs as an in-process BackgroundTask with no durable
queue. The webhook handler returns 200 to GitHub *before* file collection + the Claude review
(minutes), and the only durable record — the `Analysis` row — is written only *after* all of it.
A SIGTERM (Railway redeploy), OOM, or crash inside that window destroys the analysis with no row,
no retry, and no redelivery, leaving it indistinguishable from "not analyzed yet" forever.

This table does not prevent the loss — it makes it detectable. A row is written before the
expensive work and deleted on normal completion, so a surviving stale row means a lost analysis.

🔴 `Analysis` 와 분리한 이유: `Analysis` 에 pending 상태를 두면 `_ensure_repo`/`_save_and_gate`
의 `find_by_sha` dedup 이 **자기 자신의 pending 행을 발견**해 결과를 저장하지 않는다. 별도
테이블은 first-writer-wins 불변식(#794·#780)을 전혀 건드리지 않는다.
🔴 Kept separate from `Analysis`: a pending state on `Analysis` would make the `find_by_sha` dedup
in `_ensure_repo`/`_save_and_gate` match the row we just wrote and skip persisting the result.
A separate table leaves the first-writer-wins invariants (#794/#780) untouched.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, text,
)

from src.database import Base


# pylint: disable=too-few-public-methods
class AnalysisAttempt(Base):
    """분석 시작 흔적 — 정상 종료 시 삭제되며, 남은 행은 소실 신호다."""

    __tablename__ = "analysis_attempts"
    __table_args__ = (
        # 동일 SHA 재시작 시 행이 무한 증식하지 않도록 — 중복 INSERT 는 IntegrityError → False.
        # Prevents unbounded rows on repeated starts for one SHA — duplicate INSERT → IntegrityError.
        UniqueConstraint("repo_id", "commit_sha", name="uq_analysis_attempts_repo_sha"),
    )

    id = Column(Integer, primary_key=True, index=True)
    # repositories 삭제 시 동반 삭제 — analyses child 4종과 동일 CASCADE 정책 (db.md 매트릭스).
    # CASCADE on repository delete — same policy as the 4 analyses children (db.md matrix).
    repo_id = Column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
    )
    commit_sha = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=True)
    # "push" | "pull_request" — orphan 분류 시 어느 이벤트가 소실됐는지 식별.
    # "push" | "pull_request" — identifies which event was lost when triaging orphans.
    event = Column(String(32), nullable=True)
    # server_default 의무 — raw-SQL INSERT 가 컬럼을 생략해도 NOT NULL 위반이 안 나게 (db.md).
    # index=True 는 orphan 조회(`started_at < cutoff`) 전용 — 이 테이블의 유일한 스캔 패턴
    # (`ix_analysis_attempts_started_at` 자동 명명 — __table_args__ 중복 선언 금지).
    # server_default is mandatory so a raw-SQL INSERT omitting the column won't violate NOT NULL.
    # index=True serves the orphan lookup (`started_at < cutoff`), this table's only scan pattern
    # (auto-named ix_analysis_attempts_started_at — do not also declare it in __table_args__).
    started_at = Column(
        DateTime,
        nullable=False,
        # 🔴 naive UTC 삽입 (종합감사 P2) — 컬럼은 naive DateTime(TIMESTAMP WITHOUT TIME ZONE)이고
        #   orphan sweep 은 `_now_naive()` cutoff(naive)와 비교한다. default 가 aware 값을 넣으면
        #   PG 에서 삽입/비교가 세션 타임존에 의존해 소실 탐지가 흔들린다 → cutoff 규약과 동일하게 naive UTC.
        # Insert naive UTC to match the naive column + `_now_naive()` cutoff (PG session-tz safety).
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
