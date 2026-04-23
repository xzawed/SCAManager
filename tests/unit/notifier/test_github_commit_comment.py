"""Tests for src/notifier/github_commit_comment.py — post_commit_comment()."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest


def _make_result():
    return {
        "source": "push",
        "score": 82,
        "grade": "B",
        "breakdown": {
            "code_quality": 28, "security": 20,
            "commit_message": 17, "ai_review": 15, "test_coverage": 2,
        },
        "ai_summary": "코드가 전반적으로 양호합니다.",
        "ai_suggestions": [],
        "issues": [],
    }


def _mock_client():
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


async def test_post_commit_comment_calls_correct_url():
    from src.notifier.github_commit_comment import post_commit_comment
    with patch("src.notifier.github_commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc123def456",
            result=_make_result(),
        )

    url = mock_client.post.call_args[0][0]
    assert url == "https://api.github.com/repos/owner/repo/commits/abc123def456/comments"


async def test_post_commit_comment_body_uses_shared_formatter():
    from src.notifier.github_commit_comment import post_commit_comment
    with patch("src.notifier.github_commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            result=_make_result(),
        )

    body = mock_client.post.call_args[1]["json"]["body"]
    assert "SCAManager 분석 결과" in body
    assert "82/100" in body


async def test_post_commit_comment_auth_header():
    from src.notifier.github_commit_comment import post_commit_comment
    with patch("src.notifier.github_commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_client()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment(
            github_token="ghp_TOKEN",
            repo_name="owner/repo",
            commit_sha="abc",
            result=_make_result(),
        )

    headers = mock_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ghp_TOKEN"


async def test_post_commit_comment_httpx_error_swallowed():
    """HTTPError 시 재raise하지 않고 조용히 반환한다 (파이프라인 미중단)."""
    from src.notifier.github_commit_comment import post_commit_comment
    with patch("src.notifier.github_commit_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("boom"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_commit_comment(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            result=_make_result(),
        )


async def test_post_commit_comment_keyword_only():
    from src.notifier.github_commit_comment import post_commit_comment
    with pytest.raises(TypeError):
        await post_commit_comment("ghp_test", "owner/repo", "abc", _make_result())
