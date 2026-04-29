"""Phase 3 PR-B1 — pull_request.closed/auto_merge_disabled 라이프사이클 핸들러 테스트.

webhook → state 전이 (mark_actually_merged / mark_disabled_externally) 검증.
"""
# pylint: disable=redefined-outer-name,import-outside-toplevel
import os
from unittest.mock import MagicMock, patch

import pytest

# src 임포트 전 환경변수 주입
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")


# ────────────────── pull_request.closed merged=true ──────────────────


@pytest.mark.asyncio
async def test_handle_merged_pr_event_transitions_state_to_actually_merged():
    """pull_request.closed merged=true → mark_actually_merged 호출."""
    from src.webhook.providers.github import _handle_merged_pr_event

    data = {
        "pull_request": {"merged": True, "number": 7, "body": ""},
        "repository": {"full_name": "o/r"},
    }

    # find_latest_for_pr 가 enabled_pending_merge 행 반환
    fake_attempt = MagicMock()
    fake_attempt.id = 99
    with patch("src.webhook.providers.github.SessionLocal") as mock_session_cls, \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.find_latest_for_pr",
             return_value=fake_attempt,
         ), \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.mark_actually_merged",
             return_value=True,
         ) as mock_mark:
        # SessionLocal 컨텍스트 매니저 mock
        mock_session_cls.return_value.__enter__.return_value = MagicMock()
        mock_session_cls.return_value.__exit__.return_value = None

        result = await _handle_merged_pr_event(data)

    assert result["status"] == "accepted"
    mock_mark.assert_called_once()
    assert mock_mark.call_args.kwargs["attempt_id"] == 99


@pytest.mark.asyncio
async def test_handle_merged_pr_event_no_op_when_no_merge_attempt():
    """find_latest_for_pr 가 None 반환 시 mark_actually_merged 미호출."""
    from src.webhook.providers.github import _handle_merged_pr_event

    data = {
        "pull_request": {"merged": True, "number": 7, "body": ""},
        "repository": {"full_name": "o/r"},
    }

    with patch("src.webhook.providers.github.SessionLocal") as mock_session_cls, \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.find_latest_for_pr",
             return_value=None,
         ), \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.mark_actually_merged",
         ) as mock_mark:
        mock_session_cls.return_value.__enter__.return_value = MagicMock()
        mock_session_cls.return_value.__exit__.return_value = None

        result = await _handle_merged_pr_event(data)

    assert result["status"] == "accepted"
    mock_mark.assert_not_called()


@pytest.mark.asyncio
async def test_handle_merged_pr_event_isolates_db_failure():
    """DB 오류로 state 전이 실패해도 webhook 응답은 정상 (관측 격리)."""
    from sqlalchemy.exc import SQLAlchemyError

    from src.webhook.providers.github import _handle_merged_pr_event

    data = {
        "pull_request": {"merged": True, "number": 7, "body": ""},
        "repository": {"full_name": "o/r"},
    }

    with patch(
        "src.webhook.providers.github.SessionLocal",
        side_effect=SQLAlchemyError("connection lost"),
    ):
        # SQLAlchemyError 가 _record_actual_merge 안 try/except 에서 격리됨
        result = await _handle_merged_pr_event(data)

    # body 없어 close_issue 단계도 ignored — but record_actual_merge 격리 검증
    assert result["status"] in {"accepted", "ignored"}


# ────────────────── pull_request.auto_merge_disabled ──────────────────


@pytest.mark.asyncio
async def test_handle_auto_merge_disabled_user_inferred_reason():
    """sender.type=User 면 inferred_reason='auto_merge_disabled_by_user'."""
    from src.webhook.providers.github import _handle_auto_merge_disabled_event

    data = {
        "repository": {"full_name": "o/r"},
        "pull_request": {"number": 7},
        "sender": {"login": "xzawed", "type": "User"},
    }

    fake_attempt = MagicMock()
    fake_attempt.id = 42
    with patch("src.webhook.providers.github.SessionLocal") as mock_session_cls, \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.find_latest_for_pr",
             return_value=fake_attempt,
         ), \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.mark_disabled_externally",
             return_value=True,
         ) as mock_mark:
        mock_session_cls.return_value.__enter__.return_value = MagicMock()
        mock_session_cls.return_value.__exit__.return_value = None

        result = await _handle_auto_merge_disabled_event(data)

    assert result["status"] == "accepted"
    mock_mark.assert_called_once()
    assert mock_mark.call_args.kwargs["reason"] == "auto_merge_disabled_by_user"


@pytest.mark.asyncio
async def test_handle_auto_merge_disabled_bot_inferred_reason():
    """sender.type=Bot 면 inferred_reason='auto_merge_disabled_by_check_or_force_push'."""
    from src.webhook.providers.github import _handle_auto_merge_disabled_event

    data = {
        "repository": {"full_name": "o/r"},
        "pull_request": {"number": 7},
        "sender": {"login": "github-actions[bot]", "type": "Bot"},
    }

    fake_attempt = MagicMock()
    fake_attempt.id = 42
    with patch("src.webhook.providers.github.SessionLocal") as mock_session_cls, \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.find_latest_for_pr",
             return_value=fake_attempt,
         ), \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.mark_disabled_externally",
             return_value=True,
         ) as mock_mark:
        mock_session_cls.return_value.__enter__.return_value = MagicMock()
        mock_session_cls.return_value.__exit__.return_value = None

        await _handle_auto_merge_disabled_event(data)

    assert mock_mark.call_args.kwargs["reason"] == "auto_merge_disabled_by_check_or_force_push"


@pytest.mark.asyncio
async def test_handle_auto_merge_disabled_returns_ignored_when_no_attempt():
    """find_latest_for_pr 가 None 면 ignored 반환."""
    from src.webhook.providers.github import _handle_auto_merge_disabled_event

    data = {
        "repository": {"full_name": "o/r"},
        "pull_request": {"number": 7},
        "sender": {"login": "xzawed", "type": "User"},
    }

    with patch("src.webhook.providers.github.SessionLocal") as mock_session_cls, \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.find_latest_for_pr",
             return_value=None,
         ), \
         patch(
             "src.webhook.providers.github.merge_attempt_repo.mark_disabled_externally",
         ) as mock_mark:
        mock_session_cls.return_value.__enter__.return_value = MagicMock()
        mock_session_cls.return_value.__exit__.return_value = None

        result = await _handle_auto_merge_disabled_event(data)

    assert result["status"] == "ignored"
    mock_mark.assert_not_called()


@pytest.mark.asyncio
async def test_handle_auto_merge_disabled_missing_repo_or_pr_returns_ignored():
    """repo_name 또는 pr_number 없으면 ignored."""
    from src.webhook.providers.github import _handle_auto_merge_disabled_event

    # repo 누락
    result1 = await _handle_auto_merge_disabled_event({
        "pull_request": {"number": 7}, "sender": {"login": "x", "type": "User"},
    })
    assert result1["status"] == "ignored"

    # pr_number 누락
    result2 = await _handle_auto_merge_disabled_event({
        "repository": {"full_name": "o/r"},
        "pull_request": {},
        "sender": {"login": "x", "type": "User"},
    })
    assert result2["status"] == "ignored"


@pytest.mark.asyncio
async def test_handle_auto_merge_disabled_isolates_db_failure():
    """DB 오류로 mark_disabled_externally 실패해도 webhook 응답은 ignored (격리)."""
    from sqlalchemy.exc import SQLAlchemyError

    from src.webhook.providers.github import _handle_auto_merge_disabled_event

    data = {
        "repository": {"full_name": "o/r"},
        "pull_request": {"number": 7},
        "sender": {"login": "xzawed", "type": "User"},
    }

    with patch(
        "src.webhook.providers.github.SessionLocal",
        side_effect=SQLAlchemyError("connection lost"),
    ):
        result = await _handle_auto_merge_disabled_event(data)

    assert result["status"] == "ignored"
