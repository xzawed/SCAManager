"""GateDecision ORM 모델 — PR Gate 승인/반려 결정 이력."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from src.database import Base


# pylint: disable=too-few-public-methods
class GateDecision(Base):
    """PR Gate 승인·반려 결정 이력 테이블 (자동/반자동 모드 모두 기록)."""

    __tablename__ = "gate_decisions"
    id = Column(Integer, primary_key=True, index=True)
    # Phase H — Critical C7: ondelete=CASCADE 추가. Repository → Analysis →
    # GateDecision 삭제 사슬 일관성 보장. 미설정 시 Analysis 삭제 → FK violation.
    # `delete_repo_cascade` (ui/_helpers.py) 가 application-level 보완 중이지만,
    # 다른 경로 (admin script, future API) 에서 Analysis 삭제 시 안전망 필요.
    # MergeAttempt/MergeRetryQueue/AnalysisFeedback 은 이미 CASCADE — 일관성 확보.
    # P0-A: unique=True 추가 — gate_decision_repo.upsert() 는 분석 당 1건 upsert 이므로
    # UNIQUE constraint 필수. unique=True 는 자동으로 인덱스를 생성하므로 index=True 제거.
    # Phase H — Critical C7: add ondelete=CASCADE so direct Analysis deletion
    # propagates here too (mirrors MergeAttempt/MergeRetryQueue/AnalysisFeedback).
    # P0-A: unique=True enforces one gate_decision per analysis (upsert semantic).
    # unique=True implies an index, so index=True is dropped.
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    decision = Column(String, nullable=False)   # "approve" | "reject" | "skip"
    mode = Column(String, nullable=False)        # "auto" | "manual"
    decided_by = Column(String, nullable=True)
    decided_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    # 🔴 「결정했다」와 「GitHub 에 리뷰가 붙었다」는 다르다 (#1504 R2).
    #    수동 경로는 claim → POST 순서라, POST 가 전송 오류로 실패하면 결정만 남고 리뷰는 없다.
    #    그 상태를 표현할 수단이 없어서 재클릭이 리플레이로 막혔다 — 재시도 수단이 없었다.
    # "pending_post" = 결정은 기록됐으나 리뷰 게시가 확인되지 않았다 (재시도 대상)
    # "posted"       = 리뷰가 GitHub 에 붙었다 (리플레이로 막는다)
    # 🔴 `server_default="posted"` — 기존 행은 **게시된 것으로 본다**. `pending_post` 로
    #    채우면 만료 없는 HMAC 때문에 옛 버튼을 누르는 순간 이력 전체가 재게시된다.
    #    오늘의 결함으로 실제 미게시인 행은 갇힌 채 남지만, 이력을 GitHub 재발화로
    #    치유하지 않는 쪽이 옳다.
    # Decided is not posted: the manual path claims before posting, so a transport failure
    # leaves a decision with no review. Existing rows default to "posted" — backfilling
    # "pending_post" would re-post every historical decision on the next click.
    state = Column(String, nullable=False, server_default="posted", default="posted")
    # 🔴 게시 **진행 중** 클레임 — `state == "pending_post"` 는 잠금이 아니다.
    #    두 클릭이 둘 다 그것을 보면 둘 다 POST 해 중복 리뷰가 난다.
    #    🔴 `decided_at` 을 리스로 재사용하지 않는다 — HMAC 이 만료되지 않으므로 몇 시간 뒤
    #    클릭은 `decided_at` 이 이미 낡았고, 그러면 리스가 진입하는 순간 만료로 보여
    #    CAS 가 무력해진다(바로 그 늦은 클릭 경로에서). 별도 컬럼이 필요하다.
    # An in-flight claim: "pending_post" alone is not a lock, and decided_at cannot serve as
    # the lease because the never-expiring HMAC makes it stale on exactly the late-click path.
    post_claimed_at = Column(DateTime, nullable=True)
