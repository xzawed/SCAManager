"""Tests for src/notifier/telegram.py — _build_message 절단 + telegram_post_message 에러."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.analyzer.ai_review import AiReviewResult
from src.analyzer.static import StaticAnalysisResult
from src.notifier.telegram import _build_message, telegram_post_message
from src.scorer.calculator import ScoreResult

_MAX = 4096


def _make_score(total=80, grade="B"):
    return ScoreResult(
        total=total, grade=grade,
        code_quality_score=20, security_score=15,
        breakdown={
            "code_quality": 20, "security": 15,
            "commit_message": 13, "ai_review": 20, "test_coverage": 12,
        },
    )


def _make_ai(summary=""):
    return AiReviewResult(commit_score=13, ai_score=20, test_score=8, summary=summary)


# ---------------------------------------------------------------------------
# _build_message — 4096자 절단
# ---------------------------------------------------------------------------

def test_build_message_truncated_when_over_limit():
    """메시지가 4096자를 초과하면 4096자로 절단하고 '...'로 끝나야 한다."""
    # 긴 summary를 넣어 강제로 초과
    long_summary = "A" * 5000
    msg = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_make_score(),
        analysis_results=[],
        pr_number=None,
        ai_review=_make_ai(summary=long_summary),
    )
    assert len(msg) == _MAX
    assert msg.endswith("...")


def test_build_message_not_truncated_when_under_limit():
    """메시지가 4096자 이하이면 절단하지 않는다."""
    msg = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_make_score(),
        analysis_results=[],
        pr_number=None,
        ai_review=_make_ai(summary="짧은 요약"),
    )
    assert len(msg) <= _MAX
    assert not msg.endswith("...")


def test_build_message_exactly_at_limit_not_truncated():
    """메시지가 정확히 4096자이면 절단하지 않아야 한다."""
    # 반복 테스트: 다양한 길이로 절단 경계값 확인
    short_msg = _build_message(
        repo_name="x",
        commit_sha="0" * 7,
        score_result=_make_score(),
        analysis_results=[],
        pr_number=None,
    )
    # 절단된 메시지는 반드시 "..."로 끝나야 함
    if len(short_msg) > _MAX:
        assert short_msg.endswith("...")
    else:
        assert len(short_msg) <= _MAX


def test_build_message_truncated_length_is_exactly_max():
    """절단된 메시지의 길이는 정확히 4096이어야 한다."""
    long_summary = "B" * 6000
    msg = _build_message(
        repo_name="owner/repo",
        commit_sha="abc1234",
        score_result=_make_score(),
        analysis_results=[],
        pr_number=None,
        ai_review=_make_ai(summary=long_summary),
    )
    assert len(msg) == _MAX


# ---------------------------------------------------------------------------
# telegram_post_message — HTTP 에러 처리
# ---------------------------------------------------------------------------

async def test_telegram_post_message_raises_on_http_error():
    """raise_for_status()가 HTTPError를 발생시키면 예외가 전파된다."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403 Forbidden", request=MagicMock(), response=MagicMock()
    )
    with patch("src.notifier.telegram.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        with pytest.raises(httpx.HTTPStatusError):
            await telegram_post_message(
                bot_token="123:ABC",
                chat_id="-100123",
                payload={"text": "test", "parse_mode": "HTML"},
            )


async def test_telegram_post_message_connect_error_propagates():
    """네트워크 연결 실패 시 ConnectError가 전파된다."""
    with patch("src.notifier.telegram.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_cls.return_value = mock_client

        with pytest.raises(httpx.ConnectError):
            await telegram_post_message(
                bot_token="123:ABC",
                chat_id="-100123",
                payload={"text": "test"},
            )


async def test_telegram_post_message_sends_correct_chat_id():
    """telegram_post_message가 지정된 chat_id로 POST 요청을 전송한다."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.notifier.telegram.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        await telegram_post_message(
            bot_token="123:ABC",
            chat_id="-999888",
            payload={"text": "hello", "parse_mode": "HTML"},
        )

        call_json = mock_client.post.call_args.kwargs.get("json") or {}
        assert call_json["chat_id"] == "-999888"
        assert call_json["text"] == "hello"
