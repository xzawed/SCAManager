import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from src.gate.github_review import post_github_review


async def test_post_github_review_approve():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        await post_github_review("token", "owner/repo", 5, "approve", "LGTM")
        call_str = str(mock_client.post.call_args)
        assert "APPROVE" in call_str
        assert "owner/repo" in call_str

async def test_post_github_review_reject():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        await post_github_review("token", "owner/repo", 5, "reject", "Needs work")
        assert "REQUEST_CHANGES" in str(mock_client.post.call_args)

async def test_post_github_review_raises_on_error():
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("GitHub API error")
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        with pytest.raises(Exception, match="GitHub API error"):
            await post_github_review("token", "owner/repo", 5, "approve", "OK")


# --- merge_pr() 테스트 (Red: merge_pr 함수가 아직 존재하지 않음) ---

async def test_merge_pr_success():
    # merge_pr()이 PUT 요청 성공(200) 시 True를 반환하는지 검증
    from src.gate.github_review import merge_pr
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        result = await merge_pr("token", "owner/repo", 5)
    assert result is True
    call_args = mock_client.put.call_args
    assert "owner/repo" in call_args[0][0]
    assert "pulls/5/merge" in call_args[0][0]
    assert call_args[1]["json"]["merge_method"] == "squash"


async def test_merge_pr_custom_method():
    # merge_method 인자를 "merge"로 전달 시 PUT body에 반영되는지 검증
    from src.gate.github_review import merge_pr
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        result = await merge_pr("token", "owner/repo", 5, merge_method="merge")
    assert result is True
    call_args = mock_client.put.call_args
    assert call_args[1]["json"]["merge_method"] == "merge"


async def test_merge_pr_returns_false_on_http_error():
    # raise_for_status()에서 HTTPStatusError 발생 시 False를 반환하고 예외를 전파하지 않는지 검증
    from src.gate.github_review import merge_pr
    mock_response = MagicMock()
    mock_request = MagicMock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "405 Method Not Allowed", request=mock_request, response=mock_response
    )
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.put = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client
        result = await merge_pr("token", "owner/repo", 5)
    assert result is False


async def test_merge_pr_returns_false_on_connection_error():
    # 연결 오류(Exception) 발생 시 False를 반환하고 예외를 전파하지 않는지 검증
    from src.gate.github_review import merge_pr
    with patch("src.gate.github_review.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_cls.return_value = mock_client
        result = await merge_pr("token", "owner/repo", 5)
    assert result is False
