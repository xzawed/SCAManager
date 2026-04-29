"""Phase 4 PR-T3 — merge_retry_service.py private helper 단위 테스트.

기존 test_merge_retry_service.py 가 process_pending_retries 의 메인 시나리오를
다루지만, 14-에이전트 감사 R1-B 가 지적한 "private helper 사각지대" 가 남았다.
이 파일이 그 갭을 메운다.

검증 대상 (services/merge_retry_service.py):
  - _resolve_github_token: user 토큰 우선 / 빈 토큰 → settings fallback / repo 미존재
  - _get_pr_data: 성공 / HTTPError → None
  - _get_ci_status_safe: get_required_check_contexts HTTPError → None /
    get_ci_status HTTPError → "unknown"
  - _notify_config_changed / _notify_merge_succeeded / _notify_merge_terminal:
    chat_id None / bot_token None / HTTPError 모두 graceful
  - _create_failure_issue_safe: 예외 격리 (Exception → warning)
  - process_pending_retries: _get_pr_data None 반환 → released with pr_fetch_failed
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_settings_token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

# pylint: disable=wrong-import-position
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models.analysis import Analysis
from src.models.merge_retry import MergeRetryQueue
from src.models.repository import Repository
from src.services.merge_retry_service import (
    _create_failure_issue_safe,
    _get_ci_status_safe,
    _get_pr_data,
    _notify_config_changed,
    _notify_merge_succeeded,
    _notify_merge_terminal,
    _resolve_github_token,
    process_pending_retries,
)


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionCls = sessionmaker(bind=engine)
    session = SessionCls()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_row(repo_full_name="owner/repo", pr_number=42, score=80, attempts=1) -> MergeRetryQueue:
    """테스트용 가짜 MergeRetryQueue 객체 (DB 미저장)."""
    row = MergeRetryQueue(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        analysis_id=1,
        commit_sha="abc",
        score=score,
        threshold_at_enqueue=75,
        status="pending",
        attempts_count=attempts,
        max_attempts=30,
        notify_chat_id=None,
    )
    return row


def _make_cfg(notify_chat_id=None, auto_merge_issue_on_failure=False) -> MagicMock:
    cfg = MagicMock()
    cfg.notify_chat_id = notify_chat_id
    cfg.auto_merge_issue_on_failure = auto_merge_issue_on_failure
    return cfg


# ──────────────────────────────────────────────────────────────────────────
# _resolve_github_token
# ──────────────────────────────────────────────────────────────────────────


def test_resolve_token_returns_user_token_when_present(db_session):
    """repo 의 owner.plaintext_token 가 있으면 그 토큰을 사용."""
    user_mock = MagicMock()
    user_mock.plaintext_token = "ghp_user_token"

    repo = Repository(full_name="owner/repo", user_id=42)
    db_session.add(repo)
    db_session.commit()

    with patch("src.services.merge_retry_service.user_repo.find_by_id", return_value=user_mock):
        token = _resolve_github_token(db_session, "owner/repo")

    assert token == "ghp_user_token"


def test_resolve_token_falls_back_to_settings_when_user_id_none(db_session):
    """repo.user_id 가 None 이면 settings.github_token 사용."""
    repo = Repository(full_name="owner/repo", user_id=None)
    db_session.add(repo)
    db_session.commit()

    with patch("src.services.merge_retry_service.settings") as mock_settings:
        mock_settings.github_token = "ghp_settings_token"
        token = _resolve_github_token(db_session, "owner/repo")
    assert token == "ghp_settings_token"


def test_resolve_token_falls_back_when_user_token_empty(db_session):
    """user.plaintext_token 가 빈 문자열이면 settings 로 fallback."""
    user_mock = MagicMock()
    user_mock.plaintext_token = ""  # 만료/미설정

    repo = Repository(full_name="owner/repo", user_id=42)
    db_session.add(repo)
    db_session.commit()

    with patch("src.services.merge_retry_service.user_repo.find_by_id", return_value=user_mock), \
         patch("src.services.merge_retry_service.settings") as mock_settings:
        mock_settings.github_token = "ghp_settings_token"
        token = _resolve_github_token(db_session, "owner/repo")

    assert token == "ghp_settings_token"


def test_resolve_token_returns_none_when_repo_missing_and_no_settings(db_session):
    """repo 미존재 + settings.github_token 빈 문자열 → None."""
    with patch("src.services.merge_retry_service.settings") as mock_settings:
        mock_settings.github_token = ""
        token = _resolve_github_token(db_session, "ghost/repo")
    assert token is None


# ──────────────────────────────────────────────────────────────────────────
# _get_pr_data
# ──────────────────────────────────────────────────────────────────────────


async def test_get_pr_data_returns_json_on_success():
    """200 OK + JSON body → dict 반환."""
    fake_response = MagicMock()
    fake_response.json.return_value = {"merged": False, "head": {"sha": "x"}}
    fake_response.raise_for_status = MagicMock(return_value=None)

    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_response)

    with patch("src.services.merge_retry_service.get_http_client", return_value=fake_client):
        result = await _get_pr_data("token", "owner/repo", 42)

    assert result == {"merged": False, "head": {"sha": "x"}}


async def test_get_pr_data_returns_none_on_httperror():
    """HTTPError → None 반환 (예외 미전파)."""
    fake_client = MagicMock()
    fake_client.get = AsyncMock(side_effect=httpx.ConnectError("DNS"))

    with patch("src.services.merge_retry_service.get_http_client", return_value=fake_client):
        result = await _get_pr_data("token", "owner/repo", 42)
    assert result is None


async def test_get_pr_data_returns_none_on_4xx_status():
    """raise_for_status() 가 HTTPStatusError 던지면 None."""
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=MagicMock()),
    )
    fake_client = MagicMock()
    fake_client.get = AsyncMock(return_value=fake_response)

    with patch("src.services.merge_retry_service.get_http_client", return_value=fake_client):
        result = await _get_pr_data("token", "owner/repo", 999)
    assert result is None


# ──────────────────────────────────────────────────────────────────────────
# _get_ci_status_safe — HTTPError 폴백
# ──────────────────────────────────────────────────────────────────────────


async def test_get_ci_status_safe_required_httperror_falls_back_to_none():
    """get_required_check_contexts HTTPError → required=None 으로 통일."""
    with patch(
        "src.services.merge_retry_service.get_required_check_contexts",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("net"),
    ), patch(
        "src.services.merge_retry_service.get_ci_status",
        new_callable=AsyncMock,
        return_value="passed",
    ) as mock_ci:
        result = await _get_ci_status_safe("tok", "owner/repo", "sha")
    assert result == "passed"
    assert mock_ci.call_args.kwargs["required_contexts"] is None


async def test_get_ci_status_safe_get_ci_httperror_returns_unknown():
    """get_ci_status HTTPError → 'unknown' 반환."""
    with patch(
        "src.services.merge_retry_service.get_required_check_contexts",
        new_callable=AsyncMock,
        return_value={"ci/test"},
    ), patch(
        "src.services.merge_retry_service.get_ci_status",
        new_callable=AsyncMock,
        side_effect=httpx.ConnectError("net"),
    ):
        result = await _get_ci_status_safe("tok", "owner/repo", "sha")
    assert result == "unknown"


# ──────────────────────────────────────────────────────────────────────────
# _notify_config_changed
# ──────────────────────────────────────────────────────────────────────────


async def test_notify_config_changed_skip_when_no_chat_id():
    """chat_id None + row.notify_chat_id None + settings.telegram_chat_id 빈 문자열 → skip."""
    row = _make_row()
    row.notify_chat_id = None
    cfg = _make_cfg(notify_chat_id=None)

    with patch("src.services.merge_retry_service.settings") as mock_settings, \
         patch("src.services.merge_retry_service.telegram_post_message", new_callable=AsyncMock) as mock_send:
        mock_settings.telegram_chat_id = ""
        mock_settings.telegram_bot_token = "123:ABC"
        await _notify_config_changed(row, cfg)
    mock_send.assert_not_called()


async def test_notify_config_changed_skip_when_no_bot_token():
    """bot_token 빈 문자열 → skip."""
    row = _make_row()
    cfg = _make_cfg(notify_chat_id="-100")

    with patch("src.services.merge_retry_service.settings") as mock_settings, \
         patch("src.services.merge_retry_service.telegram_post_message", new_callable=AsyncMock) as mock_send:
        mock_settings.telegram_bot_token = ""
        await _notify_config_changed(row, cfg)
    mock_send.assert_not_called()


async def test_notify_config_changed_httperror_logged_warning(caplog):
    """telegram_post_message HTTPError → WARNING + graceful."""
    row = _make_row()
    cfg = _make_cfg(notify_chat_id="-100")

    with patch("src.services.merge_retry_service.settings") as mock_settings, \
         patch(
             "src.services.merge_retry_service.telegram_post_message",
             new_callable=AsyncMock,
             side_effect=httpx.HTTPError("boom"),
         ):
        mock_settings.telegram_bot_token = "123:ABC"
        with caplog.at_level(logging.WARNING):
            await _notify_config_changed(row, cfg)

    assert any("_notify_config_changed 전송 실패" in r.getMessage() for r in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# _notify_merge_succeeded / _notify_merge_terminal — HTTPError graceful
# ──────────────────────────────────────────────────────────────────────────


async def test_notify_merge_succeeded_httperror_logged_warning(caplog):
    """telegram_post_message HTTPError → WARNING + graceful."""
    row = _make_row()
    cfg = _make_cfg(notify_chat_id="-100")

    with patch("src.services.merge_retry_service.settings") as mock_settings, \
         patch(
             "src.services.merge_retry_service.telegram_post_message",
             new_callable=AsyncMock,
             side_effect=httpx.HTTPError("boom"),
         ):
        mock_settings.telegram_bot_token = "123:ABC"
        with caplog.at_level(logging.WARNING):
            await _notify_merge_succeeded(row, cfg)

    assert any("_notify_merge_succeeded 전송 실패" in r.getMessage() for r in caplog.records)


async def test_notify_merge_terminal_includes_advice_and_html_escapes(caplog):
    """terminal 알림에 advice + HTML escape 적용 확인."""
    row = _make_row(repo_full_name="own<er>/repo")
    cfg = _make_cfg(notify_chat_id="-100")
    captured: dict = {}

    async def fake_send(_token, _chat, payload):
        captured["text"] = payload["text"]

    with patch("src.services.merge_retry_service.settings") as mock_settings, \
         patch("src.services.merge_retry_service.telegram_post_message", new=fake_send), \
         patch(
             "src.services.merge_retry_service.get_advice",
             return_value="권장 조치: 관리자에게 요청",
         ):
        mock_settings.telegram_bot_token = "123:ABC"
        await _notify_merge_terminal(row, cfg, "branch_protection_blocked", "branch_protection_blocked")

    text = captured["text"]
    assert "권장 조치: 관리자에게 요청" in text
    # HTML escape 적용 — own<er> 가 own&lt;er&gt; 로 변환
    assert "own<er>" not in text
    assert "own&lt;er&gt;" in text


# ──────────────────────────────────────────────────────────────────────────
# _create_failure_issue_safe — 예외 격리
# ──────────────────────────────────────────────────────────────────────────


async def test_create_failure_issue_safe_isolates_exception(caplog):
    """create_merge_failure_issue 내부 예외 → WARNING + 함수 graceful 종료."""
    row = _make_row()
    cfg = _make_cfg()

    with patch(
        "src.services.merge_retry_service.create_merge_failure_issue",
        new_callable=AsyncMock,
        side_effect=RuntimeError("github 5xx"),
    ):
        with caplog.at_level(logging.WARNING):
            await _create_failure_issue_safe(
                "token", row, cfg,
                reason="branch_protection_blocked",
                reason_tag="branch_protection_blocked",
            )

    assert any("create_merge_failure_issue 실패" in r.getMessage() for r in caplog.records)


# ──────────────────────────────────────────────────────────────────────────
# process_pending_retries: pr_data None → released
# ──────────────────────────────────────────────────────────────────────────


async def test_process_pr_fetch_failed_releases(db_session):
    """_get_pr_data 가 None 반환 (404 등) → released with pr_fetch_failed."""
    repo = Repository(full_name="owner/repo")
    db_session.add(repo)
    db_session.commit()
    analysis = Analysis(repo_id=repo.id, commit_sha="abc", score=80, grade="B", result={})
    db_session.add(analysis)
    db_session.commit()

    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    row = MergeRetryQueue(
        repo_full_name="owner/repo", pr_number=42, analysis_id=analysis.id,
        commit_sha="abc", score=80, threshold_at_enqueue=75, status="pending",
        attempts_count=1, max_attempts=30,
        next_retry_at=now_naive - timedelta(seconds=10),
        notify_chat_id=None,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)

    fake_cfg = MagicMock()
    fake_cfg.auto_merge = True
    fake_cfg.merge_threshold = 75
    fake_cfg.notify_chat_id = None
    fake_cfg.auto_merge_issue_on_failure = False

    with patch("src.services.merge_retry_service._resolve_github_token", return_value="ghp"), \
         patch("src.services.merge_retry_service.get_repo_config", return_value=fake_cfg), \
         patch(
             "src.services.merge_retry_service._get_pr_data",
             new_callable=AsyncMock,
             return_value=None,
         ), \
         patch("src.services.merge_retry_service.merge_pr", new_callable=AsyncMock) as mock_merge:
        result = await process_pending_retries(db_session, only_ids=[row.id])

    # merge_pr 는 호출되지 않아야 함 (PR 데이터 미수집)
    mock_merge.assert_not_called()
    assert result["released"] == 1
    assert result["claimed"] == 1
    db_session.refresh(row)
    assert row.last_failure_reason == "pr_fetch_failed"
    assert row.claimed_at is None
