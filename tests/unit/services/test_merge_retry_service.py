"""merge_retry_service 단위 테스트 — TDD Red 단계 (Phase 12 T9).
Unit tests for merge_retry_service — TDD Red phase (Phase 12 T9).

In-memory SQLite + real DB operations, HTTP calls mocked.
인메모리 SQLite + 실제 DB 작업, HTTP 호출은 모킹.
"""
# pylint: disable=redefined-outer-name,import-outside-toplevel,confusing-with-statement
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

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
from src.services.merge_retry_service import process_pending_retries


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """인메모리 SQLite DB 세션 — 각 테스트 후 폐기.
    In-memory SQLite session — discarded after each test.
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


# ---------------------------------------------------------------------------
# Seed helper
# ---------------------------------------------------------------------------


def _seed_queue_row(  # pylint: disable=too-many-arguments
    db_session,
    *,
    status: str = "pending",
    commit_sha: str = "abc123",
    score: int = 85,
    next_retry_delta_seconds: int = -10,
    attempts_count: int = 1,
) -> MergeRetryQueue:
    """테스트용 Repository + Analysis + MergeRetryQueue 행을 삽입한다.
    Insert a Repository + Analysis + MergeRetryQueue row for testing.
    """
    # 동일 리포 재사용 — full_name 중복 방지
    # Reuse same repo — prevent full_name duplicate.
    repo = db_session.query(Repository).filter_by(full_name="owner/repo").first()
    if repo is None:
        repo = Repository(full_name="owner/repo")
        db_session.add(repo)
        db_session.commit()
    analysis = Analysis(
        repo_id=repo.id,
        commit_sha=commit_sha,
        score=score,
        grade="B",
        result={},
    )
    db_session.add(analysis)
    db_session.commit()

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    row = MergeRetryQueue(
        repo_full_name="owner/repo",
        pr_number=42,
        analysis_id=analysis.id,
        commit_sha=commit_sha,
        score=score,
        threshold_at_enqueue=75,
        status=status,
        attempts_count=attempts_count,
        max_attempts=30,
        next_retry_at=now_naive + timedelta(seconds=next_retry_delta_seconds),
        notify_chat_id="-100999",
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


# ---------------------------------------------------------------------------
# 공통 mock context builder
# Common mock context builder
# ---------------------------------------------------------------------------

_DEFAULT_PR_DATA = {"merged": False, "head": {"sha": "abc123"}, "state": "open"}


def _make_fake_cfg(
    auto_merge: bool = True,
    merge_threshold: int = 75,
    notify_chat_id: str | None = None,
    auto_merge_issue_on_failure: bool = False,
) -> MagicMock:
    """테스트용 가짜 RepoConfigData 를 생성한다.
    Build a fake RepoConfigData for tests.
    """
    cfg = MagicMock()
    cfg.auto_merge = auto_merge
    cfg.merge_threshold = merge_threshold
    cfg.notify_chat_id = notify_chat_id
    cfg.auto_merge_issue_on_failure = auto_merge_issue_on_failure
    return cfg


def _standard_patches(
    token_return="ghp_test",
    pr_data=None,
    merge_return=(True, None, "abc123"),
    ci_return="passed",
    cfg=None,
):
    """표준 mock 패치 컨텍스트를 반환하는 헬퍼.
    Helper returning a standard set of mock patches.
    """
    _pr = pr_data if pr_data is not None else dict(_DEFAULT_PR_DATA)
    _cfg = cfg if cfg is not None else _make_fake_cfg()
    return {
        "token": patch(
            "src.services.merge_retry_service._resolve_github_token",
            return_value=token_return,
        ),
        "repo_config": patch(
            "src.services.merge_retry_service.get_repo_config",
            return_value=_cfg,
        ),
        "pr_data": patch(
            "src.services.merge_retry_service._get_pr_data",
            new_callable=AsyncMock,
            return_value=_pr,
        ),
        "merge_pr": patch(
            "src.services.merge_retry_service.merge_pr",
            new_callable=AsyncMock,
            return_value=merge_return,
        ),
        "ci": patch(
            "src.services.merge_retry_service._get_ci_status_safe",
            new_callable=AsyncMock,
            return_value=ci_return,
        ),
        "notify_succeeded": patch(
            "src.services.merge_retry_service._notify_merge_succeeded",
            new_callable=AsyncMock,
        ),
        "notify_terminal": patch(
            "src.services.merge_retry_service._notify_merge_terminal",
            new_callable=AsyncMock,
        ),
        "notify_config": patch(
            "src.services.merge_retry_service._notify_config_changed",
            new_callable=AsyncMock,
        ),
        "log_attempt": patch(
            "src.services.merge_retry_service.log_merge_attempt",
        ),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProcessPendingRetries:
    """process_pending_retries 전체 시나리오 테스트.
    Full scenario tests for process_pending_retries.
    """

    # T9-1: 빈 큐는 0 카운트를 반환해야 한다
    # T9-1: Empty queue returns zero counts
    async def test_process_empty_queue_returns_zero_counts(self, db_session):
        """pending 행 없을 때 모든 카운트가 0인 dict 반환.
        When no pending rows exist, returns dict with all zero counts.
        """
        result = await process_pending_retries(db_session)
        assert result["claimed"] == 0
        assert result["succeeded"] == 0
        assert result["terminal"] == 0
        assert result["abandoned"] == 0
        assert result["released"] == 0
        assert result["skipped"] == 0

    # T9-2: 토큰 없으면 클레임 해제
    # T9-2: No token → release claim
    async def test_process_no_token_releases_claim(self, db_session):
        """토큰을 가져올 수 없는 경우 클레임 해제하고 released 카운트 증가.
        When token cannot be resolved, releases claim and increments released count.
        """
        row = _seed_queue_row(db_session)

        with patch(
            "src.services.merge_retry_service._resolve_github_token",
            return_value=None,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["claimed"] == 1
        assert result["released"] == 1
        assert result["abandoned"] == 0

        # 상태는 여전히 pending (release_claim 은 상태 변경 안 함)
        # Status remains pending (release_claim does not change status)
        db_session.refresh(row)
        assert row.status == "pending"
        # claimed_at 이 None 으로 초기화됐는지 확인
        # Check claimed_at was reset to None
        assert row.claimed_at is None

    # T9-3: 설정 변경 시 abandoned 마킹
    # T9-3: Config changed → abandoned
    async def test_process_config_changed_abandons(self, db_session):
        """설정이 변경돼 auto_merge=False 면 abandoned 마킹.
        When config changes so auto_merge=False, marks as abandoned.
        """
        row = _seed_queue_row(db_session, score=85)

        # auto_merge=False 인 가짜 설정 생성
        # Build a fake config with auto_merge=False
        fake_cfg = MagicMock()
        fake_cfg.auto_merge = False
        fake_cfg.merge_threshold = 75
        fake_cfg.notify_chat_id = None

        with (
            patch(
                "src.services.merge_retry_service._resolve_github_token",
                return_value="ghp_test",
            ),
            patch(
                "src.services.merge_retry_service.get_repo_config",
                return_value=fake_cfg,
            ),
            patch(
                "src.services.merge_retry_service._notify_config_changed",
                new_callable=AsyncMock,
            ),
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["claimed"] == 1
        assert result["abandoned"] == 1
        assert result["released"] == 0

        db_session.refresh(row)
        assert row.status == "abandoned"
        assert row.last_failure_reason == "config_changed"

    # T9-4: 이미 머지된 PR → succeeded 마킹
    # T9-4: Already merged PR → mark succeeded
    async def test_process_already_merged_marks_succeeded(self, db_session):
        """PR 이 이미 merged=True 면 succeeded 마킹, counts['succeeded']==1.
        When PR is already merged, marks succeeded and increments succeeded count.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            pr_data={"merged": True, "head": {"sha": "abc123"}, "state": "closed"},
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"] as mock_pr_data,
            patches["merge_pr"] as mock_merge,
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        # merge_pr 는 호출되지 않아야 함 (이미 머지됨)
        # merge_pr should not be called (already merged)
        mock_merge.assert_not_called()
        assert mock_pr_data.call_count == 1
        assert result["succeeded"] == 1
        assert result["claimed"] == 1

        db_session.refresh(row)
        assert row.status == "succeeded"
        assert row.last_failure_reason == "already_merged"

    # T9-5: SHA drift → abandoned
    async def test_process_sha_drift_abandons(self, db_session):
        """PR head SHA 가 큐 행의 commit_sha 와 다르면 abandoned 마킹.
        When PR head SHA differs from queue row's commit_sha, marks abandoned.
        """
        row = _seed_queue_row(db_session, commit_sha="abc123")

        patches = _standard_patches(
            pr_data={
                "merged": False,
                "head": {"sha": "different_sha"},
                "state": "open",
            },
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"] as mock_merge,
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        mock_merge.assert_not_called()
        assert result["abandoned"] == 1
        assert result["claimed"] == 1

        db_session.refresh(row)
        assert row.status == "abandoned"
        assert row.last_failure_reason == "sha_drift"

    # T9-6: 머지 성공 → 알림 전송, log_merge_attempt 호출
    # T9-6: Merge succeeds → notify, log_merge_attempt called
    async def test_process_merge_succeeds_notifies(self, db_session):
        """머지 성공 시 mark_succeeded, log_merge_attempt, _notify_merge_succeeded 호출.
        On merge success, calls mark_succeeded, log_merge_attempt, _notify_merge_succeeded.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(merge_return=(True, None, "abc123"))
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"] as mock_notify,
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["succeeded"] == 1
        assert result["claimed"] == 1
        mock_notify.assert_called_once()
        mock_log.assert_called_once()
        # log_merge_attempt 가 success=True 로 호출됐는지 확인
        # Check log_merge_attempt was called with success=True
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["success"] is True

        db_session.refresh(row)
        assert row.status == "succeeded"

    # T9-7: CI 진행 중 → 일시적 실패, 클레임 해제
    # T9-7: CI running → transient, release claim
    async def test_process_transient_ci_running_releases(self, db_session):
        """CI 진행 중이면 release_claim 호출, terminal 아님.
        When CI is running, calls release_claim, not terminal.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            merge_return=(False, "unstable_ci: state=unstable, merged=False", ""),
            ci_return="running",
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["released"] == 1
        assert result["terminal"] == 0
        assert result["claimed"] == 1
        # 일시적 실패는 log_merge_attempt 호출 안 함
        # Transient failure does not call log_merge_attempt
        mock_log.assert_not_called()

        db_session.refresh(row)
        assert row.status == "pending"
        assert row.claimed_at is None

    # T9-8: CI 실패 → terminal 마킹
    # T9-8: CI failed → terminal
    async def test_process_terminal_ci_failed_marks_terminal(self, db_session):
        """CI 실패 시 mark_terminal 호출, log_merge_attempt(success=False) 호출.
        When CI fails, calls mark_terminal and log_merge_attempt with success=False.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            merge_return=(False, "unstable_ci: state=unstable, merged=False", ""),
            ci_return="failed",
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"] as mock_notify_t,
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["terminal"] == 1
        assert result["released"] == 0
        assert result["claimed"] == 1
        mock_notify_t.assert_called_once()
        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["success"] is False

        db_session.refresh(row)
        assert row.status == "failed_terminal"
        assert row.last_failure_reason == "unstable_ci"

    # T9-9: 만료된 행 → terminal 마킹
    # T9-9: Expired row → terminal
    async def test_process_expired_row_marks_terminal(self, db_session):
        """만료된 행은 CI 상태가 running 이어도 terminal 처리.
        Expired rows are terminal even when CI status is running.
        """
        row = _seed_queue_row(db_session)

        patches = _standard_patches(
            merge_return=(False, "unstable_ci: state=unstable, merged=False", ""),
            ci_return="running",
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"] as mock_notify_t,
            patches["notify_config"],
            patches["log_attempt"] as mock_log,
            patch(
                "src.services.merge_retry_service.is_expired",
                return_value=True,
            ),
        ):
            result = await process_pending_retries(db_session, only_ids=[row.id])

        assert result["terminal"] == 1
        assert result["released"] == 0
        mock_notify_t.assert_called_once()
        mock_log.assert_called_once()

        db_session.refresh(row)
        assert row.status == "failed_terminal"

    # T9-10: 인프라 에러 → 30초 백오프로 클레임 해제
    # T9-10: Infra error → release with 30s backoff
    async def test_process_infra_error_releases_with_30s_backoff(self, db_session):
        """httpx.HTTPError 발생 시 30초 백오프로 클레임 해제, released 증가.
        On httpx.HTTPError, releases claim with 30s backoff and increments released.
        """
        import httpx

        row = _seed_queue_row(db_session)

        fake_cfg = _make_fake_cfg()
        with (
            patch(
                "src.services.merge_retry_service._resolve_github_token",
                return_value="ghp_test",
            ),
            patch(
                "src.services.merge_retry_service.get_repo_config",
                return_value=fake_cfg,
            ),
            patch(
                "src.services.merge_retry_service._get_pr_data",
                new_callable=AsyncMock,
                return_value=_DEFAULT_PR_DATA,
            ),
            patch(
                "src.services.merge_retry_service.merge_pr",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPError("connection failed"),
            ),
            patch(
                "src.services.merge_retry_service._get_ci_status_safe",
                new_callable=AsyncMock,
                return_value="unknown",
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_succeeded",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_terminal",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_config_changed",
                new_callable=AsyncMock,
            ),
            patch("src.services.merge_retry_service.log_merge_attempt"),
        ):
            now = datetime.now(timezone.utc)
            result = await process_pending_retries(
                db_session, now=now, only_ids=[row.id]
            )

        assert result["released"] == 1
        assert result["terminal"] == 0
        assert result["claimed"] == 1

        # claimed_at 이 None 으로 초기화됐는지 확인
        # Check claimed_at was reset to None
        db_session.refresh(row)
        assert row.claimed_at is None
        assert row.last_failure_reason == "infra_error"
        # 30초 백오프 확인 — 재시도 시각이 now + ~30초여야 함
        # Verify 30s backoff — retry time should be ~now + 30s
        expected = now.replace(tzinfo=None) + timedelta(seconds=30)
        delta = abs((row.next_retry_at - expected).total_seconds())
        assert delta < 5  # 5초 오차 허용 / 5s tolerance

    # T9-11: auto_merge_issue_on_failure=True 시 failure issue 생성
    # T9-11: auto_merge_issue_on_failure=True → creates failure issue
    async def test_process_terminal_creates_failure_issue_when_configured(
        self, db_session
    ):
        """cfg.auto_merge_issue_on_failure=True 이면 create_merge_failure_issue 호출.
        When cfg.auto_merge_issue_on_failure=True, calls create_merge_failure_issue.
        """
        row = _seed_queue_row(db_session)

        # auto_merge_issue_on_failure=True 로 설정 — _standard_patches cfg 파라미터 사용
        # Pass cfg with auto_merge_issue_on_failure=True via _standard_patches cfg param
        issue_cfg = _make_fake_cfg(auto_merge_issue_on_failure=True)
        patches = _standard_patches(
            merge_return=(False, "branch_protection_blocked: admin override required", ""),
            ci_return="failed",
            cfg=issue_cfg,
        )
        with (
            patches["token"],
            patches["repo_config"],
            patches["pr_data"],
            patches["merge_pr"],
            patches["ci"],
            patches["notify_succeeded"],
            patches["notify_terminal"],
            patches["notify_config"],
            patches["log_attempt"],
            patch(
                "src.services.merge_retry_service.create_merge_failure_issue",
                new_callable=AsyncMock,
            ) as mock_issue,
        ):
            result = await process_pending_retries(
                db_session, only_ids=[row.id]
            )

        assert result["terminal"] == 1
        mock_issue.assert_called_once()

    # T9-13: max_attempts 초과 행 → abandoned 처리
    # T9-13: Row exceeding max_attempts → abandoned
    async def test_process_max_attempts_exhausted_is_abandoned(self, db_session):
        """max_attempts 초과 시 abandoned 처리됨을 검증한다.
        Verify that rows exceeding max_attempts are marked abandoned.
        """
        row = _seed_queue_row(db_session, score=80)
        # 초과 상태 시뮬레이션 — attempts_count를 max_attempts와 같게 설정
        # Simulate exhaustion — set attempts_count equal to max_attempts
        row.attempts_count = row.max_attempts
        db_session.commit()

        with patch(
            "src.services.merge_retry_service._resolve_github_token",
            return_value="ghp_token",
        ):
            result = await process_pending_retries(
                db_session,
                now=datetime(2030, 1, 1, tzinfo=timezone.utc),
                only_ids=[row.id],
            )

        assert result["abandoned"] == 1
        assert result["succeeded"] == 0
        db_session.refresh(row)
        assert row.status == "abandoned"
        assert row.last_failure_reason == "max_attempts_exceeded"

    # T9-12: 여러 행 처리 — 1개 성공, 1개 terminal, 1개 released
    # T9-12: Multiple rows processed — 1 success, 1 terminal, 1 released
    async def test_process_multiple_rows_all_processed(self, db_session):
        """3개의 pending 행을 처리: 1 성공, 1 terminal, 1 released.
        Process 3 pending rows: 1 succeeds, 1 becomes terminal, 1 is released.
        """
        row1 = _seed_queue_row(db_session, commit_sha="sha_success")
        row2 = _seed_queue_row(db_session, commit_sha="sha_terminal")
        row3 = _seed_queue_row(db_session, commit_sha="sha_transient")

        # expected_sha 로 행 구분 — 각 행은 서로 다른 commit_sha 를 가짐
        # Distinguish rows by expected_sha — each row has a unique commit_sha
        def _merge_side_effect(*_args, **kwargs):
            sha = kwargs.get("expected_sha", "")
            if sha == "sha_success":
                return (True, None, sha)
            if sha == "sha_terminal":
                return (False, "branch_protection_blocked: admin required", "")
            # sha_transient
            return (False, "unstable_ci: state=unstable", "")

        # _get_pr_data 는 commit_sha 와 동일한 head.sha 를 반환해야 SHA drift 없음
        # _get_pr_data must return head.sha matching commit_sha to avoid SHA drift
        # AsyncMock side_effect 은 동기 함수도 허용 (값을 awaitable 로 감쌈)
        # AsyncMock side_effect accepts sync functions (wraps return value as awaitable)
        _call_counter = [0]  # 뮤터블 컨테이너로 클로저 변수 공유 / mutable container for closure sharing

        def _pr_data_side_effect(token, repo, pr):  # pylint: disable=unused-argument
            # 호출 순서로 SHA 결정 (순서: row1, row2, row3)
            # Determine SHA by call order (order: row1, row2, row3)
            count = _call_counter[0]
            _call_counter[0] += 1
            sha_map = {0: "sha_success", 1: "sha_terminal", 2: "sha_transient"}
            sha = sha_map.get(count, "sha_success")
            return {"merged": False, "head": {"sha": sha}, "state": "open"}

        multi_cfg = _make_fake_cfg()
        with (
            patch(
                "src.services.merge_retry_service._resolve_github_token",
                return_value="ghp_test",
            ),
            patch(
                "src.services.merge_retry_service.get_repo_config",
                return_value=multi_cfg,
            ),
            patch(
                "src.services.merge_retry_service._get_pr_data",
                new_callable=AsyncMock,
                side_effect=_pr_data_side_effect,
            ),
            patch(
                "src.services.merge_retry_service.merge_pr",
                new_callable=AsyncMock,
                side_effect=_merge_side_effect,
            ),
            patch(
                "src.services.merge_retry_service._get_ci_status_safe",
                new_callable=AsyncMock,
                return_value="running",
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_succeeded",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_merge_terminal",
                new_callable=AsyncMock,
            ),
            patch(
                "src.services.merge_retry_service._notify_config_changed",
                new_callable=AsyncMock,
            ),
            patch("src.services.merge_retry_service.log_merge_attempt"),
        ):
            result = await process_pending_retries(
                db_session,
                only_ids=[row1.id, row2.id, row3.id],
            )

        assert result["claimed"] == 3
        assert result["succeeded"] == 1
        assert result["terminal"] == 1
        assert result["released"] == 1
        assert result["abandoned"] == 0
        assert result["skipped"] == 0


# ---------------------------------------------------------------------------
# _get_ci_status_safe — 빈 set fallback 방어층 (engine.py 와 일관)
# _get_ci_status_safe — empty-set fallback defense layer (consistent with engine)
# ---------------------------------------------------------------------------


async def test_worker_get_ci_status_safe_converts_empty_set_to_none():
    """워커 측 _get_ci_status_safe 도 빈 set 을 None 으로 변환한다.

    Phase 12 — engine.py::_get_ci_status_safe 와 동일 패턴 적용.
    BPR Required Status Checks 미설정 시 빈 set 이 반환되는데, 그대로
    get_ci_status 에 전달하면 호출 측이 'failed' 라 오해할 위험이 있어
    None 으로 통일 (모든 체크 고려 의미).
    """
    from src.services.merge_retry_service import _get_ci_status_safe

    with patch(
        "src.services.merge_retry_service.get_required_check_contexts",
        new_callable=AsyncMock,
    ) as mock_required, patch(
        "src.services.merge_retry_service.get_ci_status",
        new_callable=AsyncMock,
    ) as mock_ci:
        mock_required.return_value = set()  # 빈 set — BPR 미설정 시나리오
        mock_ci.return_value = "running"

        result = await _get_ci_status_safe("token", "owner/repo", "sha123")

    assert result == "running"
    # 핵심 검증 — required_contexts 가 None 으로 전달되어야 함
    call_kwargs = mock_ci.call_args.kwargs
    assert call_kwargs.get("required_contexts") is None
