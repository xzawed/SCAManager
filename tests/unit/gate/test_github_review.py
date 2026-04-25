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
from src.gate.github_review import post_github_review, merge_pr


async def test_post_github_review_approve():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        await post_github_review("token", "owner/repo", 5, "approve", "LGTM")
        call_str = str(mock_client.post.call_args)
        assert "APPROVE" in call_str
        assert "owner/repo" in call_str

async def test_post_github_review_reject():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.post = AsyncMock(return_value=mock_response)
        await post_github_review("token", "owner/repo", 5, "reject", "Needs work")
        assert "REQUEST_CHANGES" in str(mock_client.post.call_args)

async def test_post_github_review_raises_on_error():
    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("GitHub API error")
        mock_client.post = AsyncMock(return_value=mock_response)
        with pytest.raises(Exception, match="GitHub API error"):
            await post_github_review("token", "owner/repo", 5, "approve", "OK")


# ---------------------------------------------------------------------------
# merge_pr() 기본 동작 — tuple[bool, str | None] 반환 대응
# ---------------------------------------------------------------------------

async def test_merge_pr_success():
    # PUT 성공(200) 시 (True, None) 반환 검증 — mergeable_state=clean 선행 조회
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)
        result = await merge_pr("token", "owner/repo", 5)

    assert result == (True, None)
    call_args = mock_client.put.call_args
    assert "owner/repo" in call_args[0][0]
    assert "pulls/5/merge" in call_args[0][0]
    assert call_args[1]["json"]["merge_method"] == "squash"


async def test_merge_pr_custom_method():
    # merge_method="merge" 전달 시 PUT body에 반영되고 (True, None) 반환
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)
        result = await merge_pr("token", "owner/repo", 5, merge_method="merge")

    assert result == (True, None)
    call_args = mock_client.put.call_args
    assert call_args[1]["json"]["merge_method"] == "merge"


async def test_merge_pr_returns_false_on_http_error():
    # raise_for_status()에서 HTTPStatusError 발생 시 (False, str) 반환 — 예외 전파 없음
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    mock_request = MagicMock()
    put_response.status_code = 405
    put_response.json.return_value = {"message": "Method Not Allowed"}
    put_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "405 Method Not Allowed", request=mock_request, response=put_response
    )

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)
        result = await merge_pr("token", "owner/repo", 5)

    assert result[0] is False
    assert isinstance(result[1], str)


async def test_merge_pr_returns_false_on_connection_error():
    # 연결 오류 발생 시 (False, str) 반환 — 예외 전파 없음
    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        result = await merge_pr("token", "owner/repo", 5)

    assert result[0] is False
    assert isinstance(result[1], str)


# ---------------------------------------------------------------------------
# get_pr_mergeable_state() 테스트
# ---------------------------------------------------------------------------

async def test_get_pr_mergeable_state_returns_state_string():
    """GET pulls/{N} → {"mergeable_state": "clean"} → "clean" 문자열 반환."""
    from src.gate.github_review import get_pr_mergeable_state

    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)

        state = await get_pr_mergeable_state("token", "owner/repo", 5)

    assert state == "clean"
    get_url = mock_client.get.call_args[0][0]
    assert "owner/repo" in get_url
    assert "pulls/5" in get_url


# ---------------------------------------------------------------------------
# merge_pr() mergeable_state 사전 확인 테스트
# ---------------------------------------------------------------------------

async def test_merge_pr_pre_checks_mergeable_state_clean():
    """mergeable_state="clean" 일 때 PUT merge 수행 → (True, None)."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        result = await merge_pr("token", "owner/repo", 7)

    assert result == (True, None)
    # GET(상태 조회) 1회 + PUT(실제 merge) 1회
    mock_client.get.assert_called_once()
    mock_client.put.assert_called_once()


async def test_merge_pr_skips_on_dirty_state():
    """mergeable_state="dirty" → PUT 미호출, (False, "dirty: ...") 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "dirty"}

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock()

        result = await merge_pr("token", "owner/repo", 7)

    assert result[0] is False
    assert isinstance(result[1], str)
    assert "dirty" in result[1]
    # PUT은 호출되지 않아야 한다
    # PUT must not be called.
    mock_client.put.assert_not_called()


async def test_merge_pr_retries_on_unknown_state():
    """1차 unknown → sleep → 2차 clean → merge 성공 → (True, None)."""
    # 1차 GET: unknown, 2차 GET: clean
    unknown_response = MagicMock()
    unknown_response.raise_for_status = MagicMock()
    unknown_response.json.return_value = {"mergeable_state": "unknown"}

    clean_response = MagicMock()
    clean_response.raise_for_status = MagicMock()
    clean_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with patch("src.gate.github_review.get_http_client") as mock_get:
            mock_client = AsyncMock()
            mock_get.return_value = mock_client
            # 첫 번째 GET → unknown, 두 번째 GET → clean
            mock_client.get = AsyncMock(side_effect=[unknown_response, clean_response])
            mock_client.put = AsyncMock(return_value=put_response)

            result = await merge_pr("token", "owner/repo", 7)

    assert result == (True, None)
    # sleep이 1회 이상 호출되어야 한다 (재시도 대기)
    # sleep must be called at least once (retry wait).
    mock_sleep.assert_called()
    # GET은 2회 호출 (최초 + 재시도)
    # GET must be called twice (initial + retry).
    assert mock_client.get.call_count == 2
    # PUT은 1회 호출
    # PUT must be called exactly once.
    mock_client.put.assert_called_once()


# ---------------------------------------------------------------------------
# merge_pr() HTTP 오류 코드별 반환값 검증
# ---------------------------------------------------------------------------

async def test_merge_pr_405_not_mergeable():
    """HTTP 405 → (False, "not_mergeable:...") 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.status_code = 405
    put_response.json.return_value = {"message": "Pull Request is not mergeable"}
    put_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "405", request=MagicMock(), response=put_response
    )

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        result = await merge_pr("token", "owner/repo", 7)

    assert result[0] is False
    assert isinstance(result[1], str)
    assert result[1].startswith("not_mergeable:")


async def test_merge_pr_403_forbidden():
    """HTTP 403 → (False, "permission_denied:...") 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.status_code = 403
    put_response.json.return_value = {"message": "Resource not accessible by integration"}
    put_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=put_response
    )

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        result = await merge_pr("token", "owner/repo", 7)

    assert result[0] is False
    assert isinstance(result[1], str)
    assert result[1].startswith("permission_denied:")


async def test_merge_pr_422_unprocessable():
    """HTTP 422 → (False, "unprocessable:...") 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.status_code = 422
    put_response.json.return_value = {"message": "Validation Failed"}
    put_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "422", request=MagicMock(), response=put_response
    )

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        result = await merge_pr("token", "owner/repo", 7)

    assert result[0] is False
    assert isinstance(result[1], str)
    assert result[1].startswith("unprocessable:")


async def test_merge_pr_409_conflict():
    """HTTP 409 → (False, "conflict_sha_changed:...") 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean"}

    put_response = MagicMock()
    put_response.status_code = 409
    put_response.json.return_value = {"message": "Head branch was modified"}
    put_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "409", request=MagicMock(), response=put_response
    )

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        result = await merge_pr("token", "owner/repo", 7)

    assert result[0] is False
    assert isinstance(result[1], str)
    assert result[1].startswith("conflict_sha_changed:")
