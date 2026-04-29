"""Phase 4 PR-T2 — engine.py 방어적 가드 단위 테스트.

기존 test_engine.py / test_auto_merge_enqueue.py 가 happy path 와 일부 가드를
다루지만, 14-에이전트 감사 R1-B 가 지적한 "방어 코드 사각지대" 가 남아있다.
이 파일은 그 갭을 메운다.

검증 대상 (engine.py):
  - _run_auto_merge_retry: get_pr_mergeable_state HTTPError → head_sha="" 폴백
  - _run_auto_merge: outer catch (RuntimeError / ValueError) 로 알림 스킵 방지
  - _enqueue_merge_retry: db=None / log_merge_attempt 실패 / enqueue_or_bump 실패
    각각 격리되어 파이프라인 중단 없음
  - _handle_terminal_merge_failure: log_merge_attempt / create_merge_failure_issue
    각각 독립 try/except 로 격리
  - _notify_merge_deferred: chat_id None / bot_token None / HTTPError 모두 graceful
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# pylint: disable=wrong-import-position
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.config_manager.manager import RepoConfigData
from src.gate.engine import (
    _enqueue_merge_retry,
    _handle_terminal_merge_failure,
    _notify_merge_deferred,
    _run_auto_merge,
    _run_auto_merge_retry,
)
from src.gate.native_automerge import MergeOutcome, PATH_REST_FALLBACK
from src.repositories.merge_retry_repo import EnqueueResult


# ──────────────────────────────────────────────────────────────────────────
# 공용 헬퍼
# ──────────────────────────────────────────────────────────────────────────


def _config(**kwargs) -> RepoConfigData:
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


def _enqueue_first() -> EnqueueResult:
    row = MagicMock()
    row.id = 1
    return EnqueueResult(row=row, is_first_deferral=True)


# ──────────────────────────────────────────────────────────────────────────
# _run_auto_merge_retry: get_pr_mergeable_state HTTPError 폴백
# ──────────────────────────────────────────────────────────────────────────


async def test_retry_path_handles_get_mergeable_state_httperror(caplog):
    """get_pr_mergeable_state HTTPError → head_sha="" 폴백, 폴백 후 native_enable_with_path 호출."""
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.get_pr_mergeable_state", new_callable=AsyncMock) as mock_state, \
         patch("src.gate.engine.native_enable_with_path", new_callable=AsyncMock) as mock_enable, \
         patch("src.gate.engine._handle_terminal_merge_failure", new_callable=AsyncMock) as mock_terminal, \
         patch("src.gate.engine.log_merge_attempt"):

        mock_settings.merge_retry_enabled = True
        mock_state.side_effect = httpx.ConnectError("DNS")
        mock_enable.return_value = MergeOutcome(
            ok=False, reason="permission_denied: forbidden",
            head_sha="", path=PATH_REST_FALLBACK,
        )

        with caplog.at_level(logging.WARNING):
            await _run_auto_merge_retry(
                config, "ghp_token", "owner/repo", 42, 80,
                analysis_id=1, db=mock_db,
            )

    # native_enable_with_path 는 expected_sha=None (head_sha="" 폴백 결과) 으로 호출
    mock_enable.assert_called_once()
    call_kwargs = mock_enable.call_args.kwargs
    assert call_kwargs["expected_sha"] is None
    # 터미널 처리 진입 (permission_denied 는 retriable 아님)
    mock_terminal.assert_called_once()
    # WARNING 로그가 남음
    assert any("get_pr_mergeable_state" in r.message for r in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# _run_auto_merge outer catch — RuntimeError / ValueError
# ──────────────────────────────────────────────────────────────────────────


async def test_run_auto_merge_outer_catches_runtime_error(caplog):
    """_run_auto_merge_retry 가 RuntimeError 던져도 _run_auto_merge 가 흡수."""
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock) as mock_retry:
        mock_settings.merge_retry_enabled = True
        mock_retry.side_effect = RuntimeError("unexpected")

        with caplog.at_level(logging.ERROR):
            # 예외 미전파 — 호출이 정상 반환되어야 함
            await _run_auto_merge(
                config, "ghp_token", "owner/repo", 42, 80,
                analysis_id=1, db=mock_db,
            )

    assert any("Auto Merge 실패" in r.message and "RuntimeError" in r.message
               for r in caplog.records)


async def test_run_auto_merge_outer_catches_value_error(caplog):
    """_run_auto_merge_retry 가 ValueError 던져도 _run_auto_merge 가 흡수."""
    mock_db = MagicMock()
    config = _config()

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine._run_auto_merge_retry", new_callable=AsyncMock) as mock_retry:
        mock_settings.merge_retry_enabled = True
        mock_retry.side_effect = ValueError("bad arg")

        with caplog.at_level(logging.ERROR):
            await _run_auto_merge(
                config, "ghp_token", "owner/repo", 42, 80,
                analysis_id=1, db=mock_db,
            )

    assert any("ValueError" in r.message for r in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# _enqueue_merge_retry: 격리된 try/except 검증
# ──────────────────────────────────────────────────────────────────────────


async def test_enqueue_with_db_none_logs_warning_and_returns(caplog):
    """db=None → WARNING 후 조용히 반환 (큐 호출 없음)."""
    config = _config()
    with patch("src.gate.engine.merge_retry_repo") as mock_repo:
        with caplog.at_level(logging.WARNING):
            await _enqueue_merge_retry(
                config=config, repo_name="owner/repo", pr_number=42,
                score=80, effective_sha="sha", reason_tag="unstable_ci",
                ci_status="running", analysis_id=1, db=None,
            )
        mock_repo.enqueue_or_bump.assert_not_called()
    assert any("auto-merge 큐잉 생략" in r.message for r in caplog.records)


async def test_enqueue_with_analysis_id_none_logs_warning_and_returns(caplog):
    """analysis_id=None → WARNING 후 조용히 반환."""
    mock_db = MagicMock()
    config = _config()
    with patch("src.gate.engine.merge_retry_repo") as mock_repo:
        with caplog.at_level(logging.WARNING):
            await _enqueue_merge_retry(
                config=config, repo_name="owner/repo", pr_number=42,
                score=80, effective_sha="sha", reason_tag="unstable_ci",
                ci_status="running", analysis_id=None, db=mock_db,
            )
        mock_repo.enqueue_or_bump.assert_not_called()
    assert any("auto-merge 큐잉 생략" in r.message for r in caplog.records)


async def test_enqueue_log_merge_attempt_failure_isolated(caplog):
    """deferred 기록 시 log_merge_attempt 가 예외 던져도 enqueue_or_bump 는 진행."""
    mock_db = MagicMock()
    config = _config()
    with patch("src.gate.engine.log_merge_attempt", side_effect=RuntimeError("DB down")), \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock):
        mock_repo.enqueue_or_bump.return_value = _enqueue_first()
        with caplog.at_level(logging.WARNING):
            await _enqueue_merge_retry(
                config=config, repo_name="owner/repo", pr_number=42,
                score=80, effective_sha="sha", reason_tag="unstable_ci",
                ci_status="running", analysis_id=1, db=mock_db,
            )
    # 기록 실패 후에도 큐 등록은 진행
    mock_repo.enqueue_or_bump.assert_called_once()
    assert any("merge_attempt 기록 실패" in r.message for r in caplog.records)


async def test_enqueue_or_bump_failure_isolated(caplog):
    """enqueue_or_bump 가 예외 던져도 _enqueue_merge_retry 는 graceful 반환."""
    mock_db = MagicMock()
    config = _config()
    with patch("src.gate.engine.log_merge_attempt"), \
         patch("src.gate.engine.merge_retry_repo") as mock_repo, \
         patch("src.gate.engine._notify_merge_deferred", new_callable=AsyncMock) as mock_notify:
        mock_repo.enqueue_or_bump.side_effect = RuntimeError("queue down")
        with caplog.at_level(logging.WARNING):
            # 예외 미전파
            await _enqueue_merge_retry(
                config=config, repo_name="owner/repo", pr_number=42,
                score=80, effective_sha="sha", reason_tag="unstable_ci",
                ci_status="running", analysis_id=1, db=mock_db,
            )
    # is_first_deferral 판정 불가 → 알림 미호출
    mock_notify.assert_not_called()
    assert any("enqueue_or_bump 실패" in r.message for r in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# _handle_terminal_merge_failure: 격리된 try/except
# ──────────────────────────────────────────────────────────────────────────


async def test_terminal_failure_log_merge_attempt_db_error_isolated(caplog):
    """log_merge_attempt 가 DB 에러 던져도 _notify_merge_failure 는 호출."""
    mock_db = MagicMock()
    config = _config()
    with patch("src.gate.engine.log_merge_attempt", side_effect=RuntimeError("DB")), \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_notify:
        with caplog.at_level(logging.WARNING):
            await _handle_terminal_merge_failure(
                config=config, github_token="tok", repo_name="owner/repo",
                pr_number=42, score=80,
                reason="permission_denied: x", reason_tag="permission_denied",
                analysis_id=1, db=mock_db,
            )
    # 기록 실패 후에도 알림 진행
    mock_notify.assert_called_once()
    assert any("merge_attempt 기록 실패" in r.message for r in caplog.records)


async def test_terminal_failure_create_issue_error_isolated(caplog):
    """create_merge_failure_issue 가 예외 던져도 알림 + 함수는 graceful 종료."""
    mock_db = MagicMock()
    config = _config(auto_merge_issue_on_failure=True)
    with patch("src.gate.engine.log_merge_attempt"), \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock) as mock_notify, \
         patch(
             "src.gate.engine.create_merge_failure_issue",
             new_callable=AsyncMock,
             side_effect=RuntimeError("github 5xx"),
         ):
        with caplog.at_level(logging.WARNING):
            await _handle_terminal_merge_failure(
                config=config, github_token="tok", repo_name="owner/repo",
                pr_number=42, score=80,
                reason="permission_denied: x", reason_tag="permission_denied",
                analysis_id=1, db=mock_db,
            )
    mock_notify.assert_called_once()
    assert any("create_merge_failure_issue 실패" in r.message for r in caplog.records)


async def test_terminal_failure_skips_log_when_no_db():
    """analysis_id 또는 db 가 None 이면 log_merge_attempt 호출 생략."""
    config = _config()
    with patch("src.gate.engine.log_merge_attempt") as mock_log, \
         patch("src.gate.engine._notify_merge_failure", new_callable=AsyncMock):
        await _handle_terminal_merge_failure(
            config=config, github_token="tok", repo_name="owner/repo",
            pr_number=42, score=80,
            reason="permission_denied: x", reason_tag="permission_denied",
            analysis_id=None, db=None,
        )
    mock_log.assert_not_called()


# ──────────────────────────────────────────────────────────────────────────
# _notify_merge_deferred: chat_id / bot_token / HTTPError 가드
# ──────────────────────────────────────────────────────────────────────────


async def test_notify_deferred_no_chat_id_skips():
    """chat_id=None → telegram_post_message 호출 없음."""
    with patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock) as mock_send:
        await _notify_merge_deferred(
            repo_name="owner/repo", pr_number=42, score=80, threshold=75,
            reason_tag="unstable_ci", ci_status="running", chat_id=None,
        )
    mock_send.assert_not_called()


async def test_notify_deferred_no_bot_token_skips():
    """bot_token 빈 문자열 → telegram_post_message 호출 없음."""
    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.telegram_post_message", new_callable=AsyncMock) as mock_send:
        mock_settings.telegram_bot_token = ""
        await _notify_merge_deferred(
            repo_name="owner/repo", pr_number=42, score=80, threshold=75,
            reason_tag="unstable_ci", ci_status="running", chat_id="-100",
        )
    mock_send.assert_not_called()


async def test_notify_deferred_httperror_logged_warning(caplog):
    """telegram_post_message HTTPError → WARNING + 함수 graceful 종료."""
    with patch("src.gate.engine.settings") as mock_settings, \
         patch(
             "src.gate.engine.telegram_post_message",
             new_callable=AsyncMock,
             side_effect=httpx.HTTPError("boom"),
         ):
        mock_settings.telegram_bot_token = "123:ABC"
        with caplog.at_level(logging.WARNING):
            await _notify_merge_deferred(
                repo_name="owner/repo", pr_number=42, score=80, threshold=75,
                reason_tag="unstable_ci", ci_status="running",
                chat_id="-100",
            )
    assert any("_notify_merge_deferred 전송 실패" in r.getMessage()
               for r in caplog.records)


async def test_notify_deferred_generic_exception_logged(caplog):
    """Telegram 라이브러리 내부 예외 (broad) 도 graceful warning."""
    with patch("src.gate.engine.settings") as mock_settings, \
         patch(
             "src.gate.engine.telegram_post_message",
             new_callable=AsyncMock,
             side_effect=RuntimeError("library bug"),
         ):
        mock_settings.telegram_bot_token = "123:ABC"
        with caplog.at_level(logging.WARNING):
            await _notify_merge_deferred(
                repo_name="owner/repo", pr_number=42, score=80, threshold=75,
                reason_tag="unstable_ci", ci_status="running",
                chat_id="-100",
            )
    msgs = [r.getMessage() for r in caplog.records]
    assert any("_notify_merge_deferred 전송 실패" in m and "RuntimeError" in m
               for m in msgs)


async def test_notify_deferred_html_escapes_repo_name():
    """repo_name 에 HTML 특수문자 포함 시 escape 적용."""
    captured: dict = {}

    async def fake_send(_token, _chat, payload):
        captured["text"] = payload["text"]

    with patch("src.gate.engine.settings") as mock_settings, \
         patch("src.gate.engine.telegram_post_message", new=fake_send):
        mock_settings.telegram_bot_token = "123:ABC"
        await _notify_merge_deferred(
            repo_name="own<er>/repo&", pr_number=42, score=80, threshold=75,
            reason_tag="unstable_ci", ci_status="running", chat_id="-100",
        )
    # < / > / & 가 HTML escape 되어야 함 — 원본 미포함
    text = captured["text"]
    assert "own<er>" not in text
    assert "own&lt;er&gt;/repo&amp;" in text
