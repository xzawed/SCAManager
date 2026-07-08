"""RepoConfig ORM 모델 — 리포별 분석·Gate·알림 설정."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, true
from src.constants import (
    GATE_DEFAULT_APPROVE_THRESHOLD,
    GATE_DEFAULT_REJECT_THRESHOLD,
    GATE_DEFAULT_MERGE_THRESHOLD,
)
from src.database import Base


# pylint: disable=too-few-public-methods
class RepoConfig(Base):
    """리포별 Gate·알림 설정 테이블 (approve_mode·auto_merge·채널 설정 포함)."""

    __tablename__ = "repo_configs"
    id = Column(Integer, primary_key=True, index=True)
    repo_full_name = Column(String, unique=True, nullable=False, index=True)
    pr_review_comment = Column(Boolean, default=True, nullable=False)
    approve_mode = Column(String, default="disabled", nullable=False)
    approve_threshold = Column(Integer, default=GATE_DEFAULT_APPROVE_THRESHOLD, nullable=False)
    reject_threshold = Column(Integer, default=GATE_DEFAULT_REJECT_THRESHOLD, nullable=False)
    notify_chat_id = Column(String, nullable=True)
    n8n_webhook_url = Column(String, nullable=True)
    discord_webhook_url = Column(String, nullable=True)
    slack_webhook_url = Column(String, nullable=True)
    custom_webhook_url = Column(String, nullable=True)
    email_recipients = Column(String, nullable=True)
    auto_merge = Column(Boolean, default=False, nullable=False)
    merge_threshold = Column(Integer, default=GATE_DEFAULT_MERGE_THRESHOLD, nullable=False)
    commit_comment = Column(Boolean, default=False, nullable=False)
    create_issue = Column(Boolean, default=False, nullable=False)
    hook_token = Column(String, nullable=True, unique=True)
    railway_deploy_alerts = Column(Boolean, default=False, nullable=False)
    railway_webhook_token = Column(String(64), nullable=True, unique=True)
    railway_api_token = Column(String, nullable=True)  # Fernet 암호화 저장
    auto_merge_issue_on_failure = Column(Boolean, default=False, nullable=False)
    # leaderboard_opt_in 컬럼 — 그룹 60 사용자 결정 정정 (2026-05-02) 으로 폐기.
    # alembic 0025 에서 컬럼 drop. 회귀 가드: tests/unit/services/test_analytics_service_deprecations.py

    # Phase 1 PR-1c (사이클 84) — 다국어 지원 리포별 알림 언어 override
    # Per-repo notification language override (Phase 1 PR-1c).
    # Nullable=True (NULL = 사용자 preferred_language fallback / NULL = fallback to user)
    notification_language = Column(String(5), nullable=True)

    # 리포별 Claude 코드리뷰 모델 override (Alembic 0032)
    # Per-repo Claude review model override (Alembic 0032)
    # NULL = settings.claude_review_model 전역 기본값 사용
    # NULL = fall back to settings.claude_review_model global default
    review_model = Column(String(50), nullable=True)

    # per-repo 비활성화 도구 목록 — JSON 배열, 기본값 빈 배열 (Alembic 0036)
    # Per-repo disabled analyzer names — JSON array, defaults to empty list (Alembic 0036)
    # server_default='[]' — SQLite create_all + PG 양쪽 DDL DEFAULT 적용
    # server_default='[]' — ensures DDL DEFAULT for both SQLite create_all and PostgreSQL
    disabled_tools = Column(JSON, default=list, server_default='[]', nullable=False)

    # 리포별 AI 코드리뷰(Sonnet) on/off — False 시 pipeline 이 review_code 미호출(비용 0). 인사이트 무관.
    # default True·NOT NULL (기존 리포 전부 유지). Alembic 0042.
    # server_default=true() — raw SQL INSERT(컬럼 미명시)에도 DDL 레벨 기본값 적용 보장
    # (disabled_tools 0036 패턴과 동일 — Python-side default 만으로는 raw SQL 경로 미보호).
    # Per-repo AI code review (Sonnet) on/off — False makes the pipeline skip review_code (zero cost).
    # server_default=true() ensures a DDL-level default even for raw SQL INSERTs that omit
    # this column (mirrors the disabled_tools 0036 pattern — a Python-side default alone
    # would not cover that path).
    ai_review_enabled = Column(Boolean, default=True, server_default=true(), nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    def __init__(self, **kwargs):
        kwargs.setdefault("pr_review_comment", True)
        kwargs.setdefault("ai_review_enabled", True)
        kwargs.setdefault("approve_mode", "disabled")
        kwargs.setdefault("approve_threshold", GATE_DEFAULT_APPROVE_THRESHOLD)
        kwargs.setdefault("reject_threshold", GATE_DEFAULT_REJECT_THRESHOLD)
        kwargs.setdefault("auto_merge", False)
        kwargs.setdefault("merge_threshold", GATE_DEFAULT_MERGE_THRESHOLD)
        kwargs.setdefault("commit_comment", False)
        kwargs.setdefault("create_issue", False)
        kwargs.setdefault("railway_deploy_alerts", False)
        kwargs.setdefault("auto_merge_issue_on_failure", False)
        super().__init__(**kwargs)
