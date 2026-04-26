"""Phase 12 CI-aware Auto Merge 재시도 종단간(E2E) 통합 테스트.
Phase 12 CI-aware Auto Merge retry end-to-end integration tests.

실행 범위 / Scope:
- 실제 SQLite in-memory DB (StaticPool) — DB 연산 모의 없음
- Real SQLite in-memory DB (StaticPool) — no mocking of DB operations
- GitHub API, Telegram API는 httpx 레벨에서 모의
- GitHub API and Telegram are mocked at the httpx level
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# pylint: disable=redefined-outer-name
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_retry import MergeRetryQueue
from src.models.repository import Repository
from src.repositories import merge_retry_repo
from src.services.merge_retry_service import process_pending_retries


@pytest.fixture
def db():
    """인메모리 SQLite DB 세션 (StaticPool) — 테스트마다 새 DB.
    In-memory SQLite session (StaticPool) — fresh DB per test.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_cls = sessionmaker(bind=engine)
    session = session_cls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_retry_row(
    db_session,
    *,
    status: str = "pending",
    commit_sha: str = "abc123",
    score: int = 85,
    threshold: int = 75,
    next_retry_offset_seconds: int = -60,  # 음수 = 이미 처리 예정 시각 도달
                                             # negative = already due
    attempts_count: int = 1,
    max_attempts: int = 30,
    auto_merge: bool = True,
    pr_number: int = 42,
    created_at_offset_hours: int = 0,
) -> MergeRetryQueue:
    """테스트용 Repository + Analysis + MergeRetryQueue 시드 데이터 삽입.
    Insert seed Repository + Analysis + MergeRetryQueue for tests.
    """
    from src.models.repo_config import RepoConfig  # 순환 import 방지용 지연 import
                                                    # Lazy import to avoid circular import
    repo = db_session.query(Repository).filter_by(full_name="owner/repo").first()
    if repo is None:
        repo = Repository(full_name="owner/repo")
        db_session.add(repo)
        db_session.commit()

    # RepoConfig 생성 (auto_merge + merge_threshold 설정)
    # Create RepoConfig (with auto_merge + merge_threshold)
    cfg = db_session.query(RepoConfig).filter_by(repo_full_name="owner/repo").first()
    if cfg is None:
        cfg = RepoConfig(
            repo_full_name="owner/repo",
            auto_merge=auto_merge,
            merge_threshold=threshold,
        )
        db_session.add(cfg)
        db_session.commit()
    else:
        cfg.auto_merge = auto_merge
        cfg.merge_threshold = threshold
        db_session.commit()

    analysis = Analysis(
        repo_id=repo.id, commit_sha=commit_sha, score=score, grade="B", result={},
    )
    db_session.add(analysis)
    db_session.commit()

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    created = now_naive + timedelta(hours=created_at_offset_hours)
    row = MergeRetryQueue(
        repo_full_name="owner/repo",
        pr_number=pr_number,
        analysis_id=analysis.id,
        commit_sha=commit_sha,
        score=score,
        threshold_at_enqueue=threshold,
        status=status,
        attempts_count=attempts_count,
        max_attempts=max_attempts,
        next_retry_at=now_naive + timedelta(seconds=next_retry_offset_seconds),
        notify_chat_id="-100999",
    )
    db_session.add(row)
    db_session.commit()

    # created_at 을 offset 이 있을 때만 명시적으로 덮어씀 (기본값 함수 우선순위 우회)
    # Override created_at only when offset is non-zero (bypasses default lambda priority)
    if created_at_offset_hours != 0:
        row.created_at = created
        row.updated_at = created
        db_session.commit()

    db_session.refresh(row)
    return row


def _mock_merge_success(sha: str = "abc123"):
    """merge_pr 성공 mock 반환값.
    Mock return value for a successful merge_pr call.
    """
    return (True, None, sha)


def _mock_pr_data(sha: str = "abc123", merged: bool = False) -> dict:
    """GET /pulls/{n} 응답 mock.
    Mock response for GET /pulls/{n}.
    """
    return {"merged": merged, "head": {"sha": sha}, "state": "open"}


async def test_happy_path_merge_succeeds(db):
    """행 대기 중 → process_pending_retries → merge_pr 성공 → status='succeeded'.
    Pending row → process_pending_retries → merge_pr succeeds → status='succeeded'.
    """
    row = _seed_retry_row(db, commit_sha="abc123")

    with patch("src.services.merge_retry_service._resolve_github_token", return_value="ghp_test"), \
         patch("src.services.merge_retry_service._get_pr_data", new_callable=AsyncMock,
               return_value=_mock_pr_data("abc123")), \
         patch("src.services.merge_retry_service.merge_pr", new_callable=AsyncMock,
               return_value=_mock_merge_success("abc123")), \
         patch("src.services.merge_retry_service._notify_merge_succeeded", new_callable=AsyncMock), \
         patch("src.services.merge_retry_service.log_merge_attempt"):

        counts = await process_pending_retries(db)

    db.refresh(row)
    assert row.status == "succeeded"
    assert counts["succeeded"] == 1
    assert counts["claimed"] == 1


async def test_force_push_abandon_stale_rows(db):
    """force-push 후 pull_request.synchronize → 이전 SHA pending 행 abandoned.
    After force-push, pull_request.synchronize abandons old-SHA pending rows.
    """
    row = _seed_retry_row(db, commit_sha="old_sha_111")
    assert row.status == "pending"

    # abandon_stale_for_pr 직접 호출 (synchronize 핸들러가 하는 일)
    # Call abandon_stale_for_pr directly (what the synchronize handler does)
    count = merge_retry_repo.abandon_stale_for_pr(
        db,
        repo_full_name="owner/repo",
        pr_number=42,
        current_sha="new_sha_222",  # 새 SHA — 다름
                                     # New SHA — different
    )

    db.refresh(row)
    assert count == 1
    assert row.status == "abandoned"
    assert row.last_failure_reason == "sha_drift"


async def test_cron_fallback_path_merges(db):
    """check_suite webhook 없이 cron이 process_pending_retries 를 직접 호출해 머지.
    Cron calls process_pending_retries directly (no check_suite webhook) and merges.
    """
    row = _seed_retry_row(db, commit_sha="cron_sha_456")

    with patch("src.services.merge_retry_service._resolve_github_token", return_value="ghp_test"), \
         patch("src.services.merge_retry_service._get_pr_data", new_callable=AsyncMock,
               return_value=_mock_pr_data("cron_sha_456")), \
         patch("src.services.merge_retry_service.merge_pr", new_callable=AsyncMock,
               return_value=_mock_merge_success("cron_sha_456")), \
         patch("src.services.merge_retry_service._notify_merge_succeeded", new_callable=AsyncMock), \
         patch("src.services.merge_retry_service.log_merge_attempt"):

        # cron 은 process_pending_retries 를 직접 호출 — webhook 없이도 동작
        # cron calls process_pending_retries directly — works without webhook
        counts = await process_pending_retries(db, limit=10)

    db.refresh(row)
    assert row.status == "succeeded"
    assert counts["succeeded"] == 1


async def test_config_changed_abandons_row(db):
    """재시도 대기 중 auto_merge 비활성화 → 행이 abandoned 처리됨.
    auto_merge disabled while retry is pending → row gets abandoned.
    """
    # 큐 행 삽입 후 auto_merge=False 로 설정 변경 시뮬레이션
    # Insert row, then simulate config change to auto_merge=False
    row = _seed_retry_row(db, commit_sha="cfg_sha_789", auto_merge=False)

    with patch("src.services.merge_retry_service._resolve_github_token", return_value="ghp_test"), \
         patch("src.services.merge_retry_service._notify_config_changed", new_callable=AsyncMock):

        counts = await process_pending_retries(db)

    db.refresh(row)
    assert row.status == "abandoned"
    assert row.last_failure_reason == "config_changed"
    assert counts["abandoned"] == 1


async def test_expired_row_marks_terminal(db):
    """max_age_hours 초과 행 → terminal 처리됨.
    Row older than max_age_hours → marked as failed_terminal.
    """
    # created_at 을 25시간 전으로 설정 (기본 max_age_hours=24 초과)
    # Set created_at to 25 hours ago (exceeds default max_age_hours=24)
    row = _seed_retry_row(db, commit_sha="exp_sha_999", created_at_offset_hours=-25)

    with patch("src.services.merge_retry_service._resolve_github_token", return_value="ghp_test"), \
         patch("src.services.merge_retry_service._get_pr_data", new_callable=AsyncMock,
               return_value=_mock_pr_data("exp_sha_999")), \
         patch("src.services.merge_retry_service.merge_pr", new_callable=AsyncMock,
               return_value=(False, "unstable_ci: CI still running", "exp_sha_999")), \
         patch("src.services.merge_retry_service._get_ci_status_safe", new_callable=AsyncMock,
               return_value="running"), \
         patch("src.services.merge_retry_service._notify_merge_terminal", new_callable=AsyncMock), \
         patch("src.services.merge_retry_service.log_merge_attempt"), \
         patch("src.services.merge_retry_service.settings") as mock_settings:

        mock_settings.merge_retry_worker_batch_size = 50
        mock_settings.merge_retry_max_age_hours = 24
        mock_settings.merge_retry_initial_backoff_seconds = 60
        mock_settings.merge_retry_max_backoff_seconds = 600
        mock_settings.telegram_bot_token = "123:ABC"
        mock_settings.telegram_chat_id = "-100123"

        counts = await process_pending_retries(db)

    db.refresh(row)
    assert row.status == "failed_terminal"
    assert counts["terminal"] == 1
