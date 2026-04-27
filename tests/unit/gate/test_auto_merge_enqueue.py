"""Phase 12 T8: _run_auto_merge CI-aware 재시도 큐 등록 테스트.
Phase 12 T8: Tests for _run_auto_merge CI-aware retry enqueueing behavior.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from unittest.mock import AsyncMock, MagicMock, patch

from src.gate.engine import _run_auto_merge
from src.config_manager.manager import RepoConfigData
from src.repositories.merge_retry_repo import EnqueueResult


# ---------------------------------------------------------------------------
# 공용 픽스처 헬퍼 / Shared fixture helpers
# ---------------------------------------------------------------------------

def _config(**kwargs) -> RepoConfigData:
    """테스트용 RepoConfigData 생성.
    Create a RepoConfigData instance for testing.
    """
    defaults = dict(
        repo_full_name="owner/repo",
        pr_review_comment=False,
        approve_mode="disabled",
        approve_threshold=75,
        reject_threshold=50,
        auto_merge=True,
        merge_threshold=75,
        notify_chat_id="-100999",
        auto_merge_issue_on_failure=False,
    )
    defaults.update(kwargs)
    return RepoConfigData(**defaults)


def _make_enqueue_result(*, is_first_deferral: bool) -> EnqueueResult:
    """EnqueueResult 모의 객체 생성 / Create a mock EnqueueResult."""
    row = MagicMock()
    row.id = 1
    return EnqueueResult(row=row, is_first_deferral=is_first_deferral)


# ---------------------------------------------------------------------------
# T8-1: CI 진행 중 → 재시도 큐 등록
# T8-1: CI running → enqueue for retry
# ---------------------------------------------------------------------------

async def test_run_auto_merge_enqueues_when_ci_running():
    """merge_pr 실패(unstable_ci) + CI running → enqueue_or_bump 호출, 실패 알림 없음.
    merge_pr fails (unstable_ci) + CI running → enqueue_or_bump called, no failure notification.
    """
    mock_db = MagicMock()
    config = _config()
    enqueue_result = _make_enqueue_result(is_first_deferral=True)

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main") as mock_base_ref, \
         patch("src.gate.engine.get_required_check_contexts", new_callable=AsyncMock) as mock_required, \
         patch("src.gate.engine.get_ci_status", new_callable=AsyncMock) as mock_ci, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_fail_notify, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock) as mock_deferred_notify, \
         patch("src.gate.engine.log_merge_attempt") as mock_log:

        mock_settings.merge_retry_enabled = True
        mock_settings.merge_retry_max_attempts = 30
        mock_settings.merge_retry_initial_backoff_seconds = 60
        mock_settings.telegram_chat_id = "-100123"
        mock_state.return_value = ("unknown", "sha123")
        mock_merge.return_value = (False, "unstable_ci: state=unstable", "sha123")
        mock_required.return_value = {"ci/test"}
        mock_ci.return_value = "running"
        mock_repo.enqueue_or_bump.return_value = enqueue_result

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=1, db=mock_db,
        )

        # 큐 등록 호출 확인 / Verify enqueue was called
        mock_repo.enqueue_or_bump.assert_called_once()
        call_kwargs = mock_repo.enqueue_or_bump.call_args.kwargs
        assert call_kwargs["repo_full_name"] == "owner/repo"
        assert call_kwargs["pr_number"] == 42
        assert call_kwargs["score"] == 80

        # 최초 지연 알림 호출 확인 / Verify first-deferral notification was sent
        mock_deferred_notify.assert_called_once()

        # 실패 알림은 호출되지 않아야 함 / Failure notification must NOT be called
        mock_fail_notify.assert_not_called()


# ---------------------------------------------------------------------------
# T8-2: CI 실패 → 터미널 처리 (큐 등록 없음)
# T8-2: CI failed → terminal failure (no enqueue)
# ---------------------------------------------------------------------------

async def test_run_auto_merge_terminal_when_ci_failed():
    """merge_pr 실패(unstable_ci) + CI failed → 터미널 처리, enqueue_or_bump 미호출.
    merge_pr fails (unstable_ci) + CI failed → terminal, enqueue_or_bump NOT called.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main") as mock_base_ref, \
         patch("src.gate.engine.get_required_check_contexts", new_callable=AsyncMock) as mock_required, \
         patch("src.gate.engine.get_ci_status", new_callable=AsyncMock) as mock_ci, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_fail_notify, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock) as mock_deferred_notify, \
         patch("src.gate.engine.log_merge_attempt") as mock_log:

        mock_settings.merge_retry_enabled = True
        mock_settings.merge_retry_max_attempts = 30
        mock_settings.merge_retry_initial_backoff_seconds = 60
        mock_settings.telegram_chat_id = "-100123"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_state.return_value = ("unknown", "sha123")
        mock_merge.return_value = (False, "unstable_ci: state=unstable", "sha123")
        mock_required.return_value = {"ci/test"}
        mock_ci.return_value = "failed"

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=1, db=mock_db,
        )

        # 큐 등록 없음 / No enqueue
        mock_repo.enqueue_or_bump.assert_not_called()

        # 지연 알림 없음 / No deferred notification
        mock_deferred_notify.assert_not_called()

        # 실패 알림 호출 / Failure notification called
        mock_fail_notify.assert_called_once()


# ---------------------------------------------------------------------------
# T8-3: 머지 성공 → 큐 등록 없음, 알림 없음
# T8-3: Merge success → no enqueue, no notifications
# ---------------------------------------------------------------------------

async def test_run_auto_merge_success_no_enqueue():
    """merge_pr 성공 → enqueue_or_bump 미호출, 실패 알림 없음.
    merge_pr success → enqueue_or_bump NOT called, no failure notification.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main") as mock_base_ref, \
         patch("src.gate.engine.get_required_check_contexts", new_callable=AsyncMock) as mock_required, \
         patch("src.gate.engine.get_ci_status", new_callable=AsyncMock) as mock_ci, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_fail_notify, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock) as mock_deferred_notify, \
         patch("src.gate.engine.log_merge_attempt") as mock_log:

        mock_settings.merge_retry_enabled = True
        mock_settings.telegram_chat_id = "-100123"
        mock_state.return_value = ("clean", "sha123")
        mock_merge.return_value = (True, None, "sha123")

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=1, db=mock_db,
        )

        # 성공 경로에서는 큐 등록 없음 / No enqueue on success path
        mock_repo.enqueue_or_bump.assert_not_called()
        mock_fail_notify.assert_not_called()
        mock_deferred_notify.assert_not_called()


# ---------------------------------------------------------------------------
# T8-4: 터미널 실패 (dirty_conflict) → 큐 등록 없음
# T8-4: Terminal failure (dirty_conflict) → no enqueue
# ---------------------------------------------------------------------------

async def test_run_auto_merge_terminal_on_dirty_conflict():
    """merge_pr 실패(dirty_conflict) → 터미널 처리, enqueue_or_bump 미호출.
    merge_pr fails (dirty_conflict) → terminal, enqueue_or_bump NOT called.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main") as mock_base_ref, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_fail_notify, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock) as mock_deferred_notify, \
         patch("src.gate.engine.log_merge_attempt") as mock_log:

        mock_settings.merge_retry_enabled = True
        mock_settings.merge_retry_max_attempts = 30
        mock_settings.telegram_chat_id = "-100123"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_state.return_value = ("dirty", "sha123")
        # dirty_conflict 는 merge_pr 사전 차단 경로에서 직접 반환됨
        # dirty_conflict is returned directly from the merge_pr pre-check path
        mock_merge.return_value = (False, "dirty_conflict: 머지 조건 미충족 (state=dirty)", "sha123")

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=1, db=mock_db,
        )

        # 터미널 태그 → 큐 등록 없음 / Terminal tag → no enqueue
        mock_repo.enqueue_or_bump.assert_not_called()
        mock_deferred_notify.assert_not_called()
        mock_fail_notify.assert_called_once()


# ---------------------------------------------------------------------------
# T8-5: 두 번째 지연 → 최초 지연 알림 없음
# T8-5: Second deferral → no deferred notification (already notified)
# ---------------------------------------------------------------------------

async def test_run_auto_merge_deferred_no_notify_on_bump():
    """두 번째 지연(is_first_deferral=False) → _notify_merge_deferred 미호출.
    Second deferral (is_first_deferral=False) → _notify_merge_deferred NOT called.
    """
    mock_db = MagicMock()
    config = _config()
    enqueue_result = _make_enqueue_result(is_first_deferral=False)

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main") as mock_base_ref, \
         patch("src.gate.engine.get_required_check_contexts", new_callable=AsyncMock) as mock_required, \
         patch("src.gate.engine.get_ci_status", new_callable=AsyncMock) as mock_ci, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_fail_notify, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock) as mock_deferred_notify, \
         patch("src.gate.engine.log_merge_attempt") as mock_log:

        mock_settings.merge_retry_enabled = True
        mock_settings.merge_retry_max_attempts = 30
        mock_settings.merge_retry_initial_backoff_seconds = 60
        mock_settings.telegram_chat_id = "-100123"
        mock_state.return_value = ("unknown", "sha123")
        mock_merge.return_value = (False, "unstable_ci: state=unstable", "sha123")
        mock_required.return_value = {"ci/test"}
        mock_ci.return_value = "running"
        mock_repo.enqueue_or_bump.return_value = enqueue_result  # is_first_deferral=False

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=1, db=mock_db,
        )

        # 두 번째 지연: 알림 없음 / Second deferral: no notification
        mock_deferred_notify.assert_not_called()
        mock_fail_notify.assert_not_called()
        # 큐 등록은 여전히 호출됨 / Enqueue is still called
        mock_repo.enqueue_or_bump.assert_called_once()


# ---------------------------------------------------------------------------
# T8-6: 점수 기준 미달 → merge_pr 미호출
# T8-6: Score below threshold → merge_pr NOT called
# ---------------------------------------------------------------------------

async def test_run_auto_merge_skips_when_score_below_threshold():
    """auto_merge=True, score=60, merge_threshold=75 → merge_pr 미호출.
    auto_merge=True, score=60, merge_threshold=75 → merge_pr NOT called.
    """
    config = _config(auto_merge=True, merge_threshold=75)

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo:

        mock_settings.merge_retry_enabled = True

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 60,  # score=60 < threshold=75
            analysis_id=1, db=MagicMock(),
        )

        # 조건 미충족 시 즉시 반환 / Early return when conditions not met
        mock_merge.assert_not_called()
        mock_repo.enqueue_or_bump.assert_not_called()


# ---------------------------------------------------------------------------
# T8-7: auto_merge=False → merge_pr 미호출
# T8-7: auto_merge disabled → merge_pr NOT called
# ---------------------------------------------------------------------------

async def test_run_auto_merge_skips_when_auto_merge_disabled():
    """auto_merge=False → merge_pr 미호출.
    auto_merge=False → merge_pr NOT called.
    """
    config = _config(auto_merge=False, merge_threshold=75)

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo:

        mock_settings.merge_retry_enabled = True

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 90,  # score >= threshold but auto_merge=False
            analysis_id=1, db=MagicMock(),
        )

        # auto_merge=False 이므로 즉시 반환 / Early return when auto_merge=False
        mock_merge.assert_not_called()
        mock_repo.enqueue_or_bump.assert_not_called()


# ---------------------------------------------------------------------------
# T8-8: merge_retry_enabled=False → 레거시 단일 시도 경로 사용
# T8-8: merge_retry_enabled=False → use legacy single-attempt path
# ---------------------------------------------------------------------------

async def test_run_auto_merge_uses_legacy_when_retry_disabled():
    """settings.merge_retry_enabled=False → 레거시 경로 사용 (enqueue 없음).
    settings.merge_retry_enabled=False → legacy path used (no enqueue).
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine._run_auto_merge_legacy", new_callable=AsyncMock) as mock_legacy, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo:

        # 레거시 경로 강제 활성화 / Force legacy path
        mock_settings.merge_retry_enabled = False

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=1, db=mock_db,
        )

        # 레거시 함수가 호출되어야 함 / Legacy function must be called
        mock_legacy.assert_called_once()

        # 큐 등록 없음 / No enqueue
        mock_repo.enqueue_or_bump.assert_not_called()


# ---------------------------------------------------------------------------
# T8-9: CI 상태 조회 실패 → 터미널 처리 (안전 기본값)
# T8-9: CI status check fails → terminal (safe default)
# ---------------------------------------------------------------------------

async def test_run_auto_merge_terminal_when_ci_status_unknown():
    """get_ci_status가 'unknown' 반환 → should_retry=False → 터미널 처리.
    get_ci_status returns 'unknown' → should_retry=False → terminal failure.
    """
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main") as mock_base_ref, \
         patch("src.gate.engine.get_required_check_contexts", new_callable=AsyncMock) as mock_required, \
         patch("src.gate.engine.get_ci_status", new_callable=AsyncMock) as mock_ci, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_fail_notify, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock) as mock_deferred_notify, \
         patch("src.gate.engine.log_merge_attempt") as mock_log:

        mock_settings.merge_retry_enabled = True
        mock_settings.telegram_chat_id = "-100123"
        mock_settings.telegram_bot_token = "123:ABC"
        mock_state.return_value = ("unknown", "sha123")
        mock_merge.return_value = (False, "unstable_ci: state=unstable", "sha123")
        mock_required.return_value = {"ci/test"}
        # CI 상태를 알 수 없음 → should_retry(unstable_ci, "unknown") = False
        # CI status unknown → should_retry(unstable_ci, "unknown") = False
        mock_ci.return_value = "unknown"

        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=1, db=mock_db,
        )

        # unknown CI 상태 → 재시도 불가 → 터미널 / Unknown CI → no retry → terminal
        mock_repo.enqueue_or_bump.assert_not_called()
        mock_deferred_notify.assert_not_called()
        mock_fail_notify.assert_called_once()


# ---------------------------------------------------------------------------
# T8-10: analysis_id/db 없음 → enqueue 생략, 예외 없음
# T8-10: No analysis_id/db → skip enqueue, no exception
# ---------------------------------------------------------------------------

async def test_run_auto_merge_no_analysis_id_skips_enqueue():
    """analysis_id=None 시 재시도 큐 등록을 생략하고 예외 없이 완료.
    When analysis_id=None, skip retry queue and complete without exception.
    """
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.merge_pr", new_callable=AsyncMock) as mock_merge, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.get_pr_base_ref", new_callable=AsyncMock, return_value="main") as mock_base_ref, \
         patch("src.gate.engine.get_required_check_contexts", new_callable=AsyncMock) as mock_required, \
         patch("src.gate.engine.get_ci_status", new_callable=AsyncMock) as mock_ci, \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock), \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock):

        mock_settings.merge_retry_enabled = True
        mock_state.return_value = ("unknown", "sha123")
        mock_merge.return_value = (False, "unstable_ci: CI 진행 중", "sha123")
        mock_required.return_value = {"ci/test"}
        mock_ci.return_value = "running"

        # analysis_id=None, db=None → 큐 등록 생략 / Skip enqueue when ids are None
        await _run_auto_merge(
            config, "ghp_token", "owner/repo", 42, 80,
            analysis_id=None, db=None,
        )

        # 예외 없이 완료, 큐 등록 없음 / Completes without exception, no enqueue
        mock_repo.enqueue_or_bump.assert_not_called()
