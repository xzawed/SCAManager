"""check_suite.completed + pull_request.synchronize webhook 핸들러 단위 테스트 (Phase 12 T11).
Unit tests for check_suite.completed and pull_request.synchronize handlers (Phase 12 T11).
"""
# pylint: disable=redefined-outer-name
import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from fastapi import BackgroundTasks  # noqa: E402


def _make_background_tasks() -> BackgroundTasks:
    """테스트용 BackgroundTasks 인스턴스를 생성한다.
    Create a BackgroundTasks instance for testing.
    """
    return BackgroundTasks()


@pytest.fixture(autouse=True)
def clear_debounce_cache():
    """각 테스트 전후 debounce 캐시를 초기화한다.
    Clear the debounce cache before and after each test.
    """
    import src.webhook.providers.github as gh_module  # pylint: disable=import-outside-toplevel
    gh_module._check_suite_debounce.clear()
    yield
    gh_module._check_suite_debounce.clear()


async def test_check_suite_completed_accepted():
    """check_suite.completed 이벤트 → 'accepted' 반환, background task 등록.
    check_suite.completed event → returns 'accepted', schedules background task.
    """
    import src.webhook.providers.github as gh_module  # pylint: disable=import-outside-toplevel

    data = {
        "action": "completed",
        "check_suite": {"head_sha": "abc123def456"},
        "repository": {"full_name": "owner/repo"},
    }
    bt = _make_background_tasks()
    result = await gh_module._handle_check_suite_completed(data, bt)
    assert result["status"] == "accepted"
    assert len(bt.tasks) == 1


async def test_check_suite_non_completed_ignored():
    """check_suite.requested 이벤트 → 'ignored' 반환, task 없음.
    check_suite.requested event → 'ignored', no background task.
    """
    import src.webhook.providers.github as gh_module  # pylint: disable=import-outside-toplevel

    data = {
        "action": "requested",
        "check_suite": {"head_sha": "abc123"},
        "repository": {"full_name": "owner/repo"},
    }
    bt = _make_background_tasks()
    result = await gh_module._handle_check_suite_completed(data, bt)
    assert result["status"] == "ignored"
    assert len(bt.tasks) == 0


async def test_check_suite_missing_sha_ignored():
    """head_sha 없는 check_suite 이벤트 → 'ignored'.
    check_suite event with missing head_sha → 'ignored'.
    """
    import src.webhook.providers.github as gh_module  # pylint: disable=import-outside-toplevel

    data = {
        "action": "completed",
        "check_suite": {},
        "repository": {"full_name": "owner/repo"},
    }
    bt = _make_background_tasks()
    result = await gh_module._handle_check_suite_completed(data, bt)
    assert result["status"] == "ignored"


async def test_check_suite_debounce_suppresses_duplicate():
    """동일 (repo, sha) 30초 내 두 번째 호출 → 'debounced'.
    Second call for same (repo, sha) within 30s → 'debounced'.
    """
    from src.webhook.providers.github import _handle_check_suite_completed  # pylint: disable=import-outside-toplevel

    data = {
        "action": "completed",
        "check_suite": {"head_sha": "abc123"},
        "repository": {"full_name": "owner/repo"},
    }
    bt1 = _make_background_tasks()
    r1 = await _handle_check_suite_completed(data, bt1)
    assert r1["status"] == "accepted"

    bt2 = _make_background_tasks()
    r2 = await _handle_check_suite_completed(data, bt2)
    assert r2["status"] == "debounced"
    assert len(bt2.tasks) == 0


async def test_check_suite_debounce_allows_after_ttl(monkeypatch):
    """30초 TTL 경과 후 동일 (repo, sha) → 다시 'accepted'.
    Same (repo, sha) after 30s TTL → 'accepted' again.
    """
    import src.webhook.providers.github as gh_module  # pylint: disable=import-outside-toplevel

    data = {
        "action": "completed",
        "check_suite": {"head_sha": "abc123"},
        "repository": {"full_name": "owner/repo"},
    }

    # 첫 번째 호출 — accepted
    # First call — accepted
    bt1 = _make_background_tasks()
    r1 = await gh_module._handle_check_suite_completed(data, bt1)
    assert r1["status"] == "accepted"

    # 캐시의 타임스탬프를 31초 전으로 되돌림 (TTL 만료 시뮬레이션)
    # Backdate cache timestamp by 31s to simulate TTL expiry
    key = ("owner/repo", "abc123")
    gh_module._check_suite_debounce[key] -= 31.0

    bt2 = _make_background_tasks()
    r2 = await gh_module._handle_check_suite_completed(data, bt2)
    assert r2["status"] == "accepted"


async def test_pr_synchronize_calls_abandon_stale():
    """pull_request.synchronize 이벤트 → abandon_stale_for_pr 호출.
    pull_request.synchronize event → calls abandon_stale_for_pr.
    """
    from unittest.mock import MagicMock, patch  # pylint: disable=import-outside-toplevel

    from src.webhook.providers.github import _handle_pr_synchronize  # pylint: disable=import-outside-toplevel

    data = {
        "action": "synchronize",
        "number": 42,
        "pull_request": {"head": {"sha": "new_sha_789"}, "number": 42},
        "repository": {"full_name": "owner/repo"},
    }

    with patch("src.webhook.providers.github.SessionLocal") as mock_session_cls, \
         patch("src.webhook.providers.github.merge_retry_repo") as mock_repo:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_repo.abandon_stale_for_pr.return_value = 1

        await _handle_pr_synchronize(data)

        mock_repo.abandon_stale_for_pr.assert_called_once_with(
            mock_db,
            repo_full_name="owner/repo",
            pr_number=42,
            current_sha="new_sha_789",
        )


async def test_trigger_retry_for_sha_calls_process_pending():
    """_trigger_retry_for_sha → process_pending_retries with correct ids.
    _trigger_retry_for_sha calls process_pending_retries with the IDs of pending rows.
    """
    from unittest.mock import AsyncMock, MagicMock, patch  # pylint: disable=import-outside-toplevel

    from src.webhook.providers.github import _trigger_retry_for_sha  # pylint: disable=import-outside-toplevel

    mock_row = MagicMock()
    mock_row.id = 99

    with patch("src.webhook.providers.github.SessionLocal") as mock_session_cls, \
         patch("src.webhook.providers.github.merge_retry_repo") as mock_repo, \
         patch(
             "src.webhook.providers.github.process_pending_retries",
             new_callable=AsyncMock,
         ) as mock_process:

        mock_db = MagicMock()
        mock_session_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_repo.find_pending_by_sha.return_value = [mock_row]
        mock_process.return_value = {
            "claimed": 1,
            "succeeded": 1,
            "terminal": 0,
            "abandoned": 0,
            "released": 0,
            "skipped": 0,
        }

        await _trigger_retry_for_sha("owner/repo", "abc123")

        mock_repo.find_pending_by_sha.assert_called_once_with(
            mock_db,
            repo_full_name="owner/repo",
            commit_sha="abc123",
        )
        mock_process.assert_called_once_with(mock_db, only_ids=[99])
