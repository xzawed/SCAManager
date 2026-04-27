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
# merge_pr() 기본 동작 — tuple[bool, str | None, str] 반환 대응
# merge_pr() basic behavior — tuple[bool, str | None, str] return value tests
# ---------------------------------------------------------------------------

async def test_merge_pr_success():
    # PUT 성공(200) 시 (True, None, head_sha) 반환 검증 — mergeable_state=clean 선행 조회
    # Verifies (True, None, head_sha) on PUT success (200) — mergeable_state=clean pre-check
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "abc123"}}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)
        result = await merge_pr("token", "owner/repo", 5)

    assert result == (True, None, "abc123")
    call_args = mock_client.put.call_args
    assert "owner/repo" in call_args[0][0]
    assert "pulls/5/merge" in call_args[0][0]
    assert call_args[1]["json"]["merge_method"] == "squash"


async def test_merge_pr_custom_method():
    # merge_method="merge" 전달 시 PUT body에 반영되고 (True, None, head_sha) 반환
    # Verifies merge_method="merge" is reflected in PUT body and returns (True, None, head_sha)
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "def456"}}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)
        result = await merge_pr("token", "owner/repo", 5, merge_method="merge")

    assert result == (True, None, "def456")
    call_args = mock_client.put.call_args
    assert call_args[1]["json"]["merge_method"] == "merge"


async def test_merge_pr_returns_false_on_http_error():
    # raise_for_status()에서 HTTPStatusError 발생 시 (False, str, head_sha) 반환 — 예외 전파 없음
    # Returns (False, str, head_sha) when raise_for_status raises HTTPStatusError — no exception propagation
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "abc111"}}

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
    assert result[2] == "abc111"


async def test_merge_pr_returns_false_on_connection_error():
    # 연결 오류 발생 시 (False, str, "") 반환 — 예외 전파 없음
    # Returns (False, str, "") on connection error — no exception propagation
    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        result = await merge_pr("token", "owner/repo", 5)

    assert result[0] is False
    assert isinstance(result[1], str)
    # head_sha 는 연결 오류 시 "" 반환
    # head_sha is "" on connection error
    assert result[2] == ""


# ---------------------------------------------------------------------------
# get_pr_mergeable_state() 테스트 — Phase 12 T7: tuple[str, str] 반환
# get_pr_mergeable_state() tests — Phase 12 T7: returns tuple[str, str]
# ---------------------------------------------------------------------------

async def test_get_pr_mergeable_state_returns_tuple():
    """GET pulls/{N} → {"mergeable_state": "clean", "head": {"sha": "def456"}} → ("clean", "def456") 반환."""
    from src.gate.github_review import get_pr_mergeable_state

    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "def456"}}

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)

        result = await get_pr_mergeable_state("token", "owner/repo", 5)

    assert result == ("clean", "def456")
    get_url = mock_client.get.call_args[0][0]
    assert "owner/repo" in get_url
    assert "pulls/5" in get_url


async def test_get_pr_mergeable_state_missing_head_sha():
    """head.sha 누락 시 ("clean", "") 반환 — 기본값 빈 문자열.
    Returns ("clean", "") when head.sha is missing — default is empty string.
    """
    from src.gate.github_review import get_pr_mergeable_state

    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    # head 키 없음 — sha 기본값 검증
    # head key absent — verifies sha default
    get_response.json.return_value = {"mergeable_state": "blocked"}

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)

        state, head_sha = await get_pr_mergeable_state("token", "owner/repo", 3)

    assert state == "blocked"
    assert head_sha == ""


# ---------------------------------------------------------------------------
# F1: get_pr_base_ref — PR base 브랜치 동적 추출
# F1: get_pr_base_ref — dynamic base ref extraction
# ---------------------------------------------------------------------------


async def test_get_pr_base_ref_returns_actual_base():
    """GET pulls/{N} → base.ref 정상 반환 — develop 같은 main 외 브랜치 인식."""
    from src.gate.github_review import get_pr_base_ref

    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"base": {"ref": "develop"}}

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)

        result = await get_pr_base_ref("token", "owner/repo", 7)

    assert result == "develop"


async def test_get_pr_base_ref_falls_back_on_http_error():
    """네트워크/HTTP 오류 → fallback("main") 반환, 예외 전파 안 함.
    Returns fallback on HTTP error without raising.
    """
    from src.gate.github_review import get_pr_base_ref

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("DNS"))

        result = await get_pr_base_ref("token", "owner/repo", 7)

    assert result == "main"


async def test_get_pr_base_ref_falls_back_on_missing_base_key():
    """응답에 base 키 누락 시 fallback("main") 반환.
    Falls back to default when base key is missing in response.
    """
    from src.gate.github_review import get_pr_base_ref

    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {}  # base 누락

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)

        result = await get_pr_base_ref("token", "owner/repo", 7, fallback="staging")

    assert result == "staging"


# ---------------------------------------------------------------------------
# merge_pr() mergeable_state 사전 확인 테스트
# merge_pr() mergeable_state pre-check tests
# ---------------------------------------------------------------------------

async def test_merge_pr_pre_checks_mergeable_state_clean():
    """mergeable_state="clean" 일 때 PUT merge 수행 → (True, None, head_sha)."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "abc999"}}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        result = await merge_pr("token", "owner/repo", 7)

    assert result == (True, None, "abc999")
    # GET(상태 조회) 1회 + PUT(실제 merge) 1회
    # GET (state check) 1 time + PUT (actual merge) 1 time
    mock_client.get.assert_called_once()
    mock_client.put.assert_called_once()


async def test_merge_pr_skips_on_dirty_state():
    """mergeable_state="dirty" → PUT 미호출, (False, "dirty: ...", head_sha) 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "dirty", "head": {"sha": "ghi789"}}

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock()

        result = await merge_pr("token", "owner/repo", 7)

    assert result[0] is False
    assert isinstance(result[1], str)
    assert "dirty" in result[1]
    # head_sha 는 dirty 상태에서도 반환됨
    # head_sha is returned even in dirty state
    assert result[2] == "ghi789"
    # PUT은 호출되지 않아야 한다
    # PUT must not be called.
    mock_client.put.assert_not_called()


async def test_merge_pr_retries_on_unknown_state():
    """1차 unknown → sleep → 2차 clean → merge 성공 → (True, None, head_sha)."""
    # 1차 GET: unknown, 2차 GET: clean
    # 1st GET: unknown, 2nd GET: clean
    unknown_response = MagicMock()
    unknown_response.raise_for_status = MagicMock()
    unknown_response.json.return_value = {"mergeable_state": "unknown", "head": {"sha": "sha_unknown"}}

    clean_response = MagicMock()
    clean_response.raise_for_status = MagicMock()
    clean_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "sha_clean"}}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        with patch("src.gate.github_review.get_http_client") as mock_get:
            mock_client = AsyncMock()
            mock_get.return_value = mock_client
            # 첫 번째 GET → unknown, 두 번째 GET → clean
            # First GET → unknown, second GET → clean
            mock_client.get = AsyncMock(side_effect=[unknown_response, clean_response])
            mock_client.put = AsyncMock(return_value=put_response)

            result = await merge_pr("token", "owner/repo", 7)

    # 최종 상태(clean)의 head_sha 사용
    # Uses head_sha from the final state (clean)
    assert result == (True, None, "sha_clean")
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
# merge_pr() HTTP error code return value tests
# ---------------------------------------------------------------------------

async def test_merge_pr_405_not_mergeable():
    """HTTP 405 → (False, "not_mergeable:...", head_sha) 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "sha405"}}

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
    assert result[2] == "sha405"


async def test_merge_pr_403_forbidden():
    """HTTP 403 → (False, "permission_denied:...", head_sha) 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "sha403"}}

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
    assert result[2] == "sha403"


async def test_merge_pr_422_unprocessable():
    """HTTP 422 → (False, "unprocessable:...", head_sha) 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "sha422"}}

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
    assert result[2] == "sha422"


async def test_merge_pr_409_conflict():
    """HTTP 409 → (False, "conflict_sha_changed:...", head_sha) 반환."""
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "sha409"}}

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
    assert result[2] == "sha409"


# ---------------------------------------------------------------------------
# Phase 12 T7 — expected_sha atomicity guard 테스트
# Phase 12 T7 — expected_sha atomicity guard tests
# ---------------------------------------------------------------------------

async def test_merge_pr_includes_sha_in_put_body_when_expected_sha_provided():
    """expected_sha 전달 시 PUT body에 {"sha": expected_sha} 포함 — GitHub 409 atomicity guard.
    When expected_sha is provided, PUT body includes {"sha": expected_sha} — GitHub 409 atomicity guard.
    """
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "abc123"}}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        result = await merge_pr("token", "owner/repo", 5, expected_sha="abc123")

    # PUT body에 "sha" 키가 포함되어야 함
    # PUT body must include "sha" key
    put_body = mock_client.put.call_args[1]["json"]
    assert put_body.get("sha") == "abc123"
    # 성공 시 (True, None, head_sha) 반환
    # Returns (True, None, head_sha) on success
    assert result == (True, None, "abc123")


async def test_merge_pr_excludes_sha_from_put_body_when_expected_sha_is_none():
    """expected_sha=None(기본값) 시 PUT body에 "sha" 키 미포함 — 기존 동작 유지.
    When expected_sha=None (default), PUT body does not include "sha" key — preserves existing behavior.
    """
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "clean", "head": {"sha": "abc123"}}

    put_response = MagicMock()
    put_response.raise_for_status = MagicMock()

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock(return_value=put_response)

        # expected_sha 없이 호출 — 기본값 None
        # Call without expected_sha — default is None
        result = await merge_pr("token", "owner/repo", 5)

    put_body = mock_client.put.call_args[1]["json"]
    # "sha" 키가 PUT body에 없어야 함
    # "sha" key must NOT be in PUT body
    assert "sha" not in put_body
    assert result == (True, None, "abc123")


async def test_merge_pr_returns_head_sha_on_failure():
    """mergeable_state="dirty" 시 (False, reason, head_sha) — head_sha 는 GET 응답에서 추출.
    When mergeable_state="dirty": (False, reason, head_sha) — head_sha extracted from GET response.
    """
    get_response = MagicMock()
    get_response.raise_for_status = MagicMock()
    get_response.json.return_value = {"mergeable_state": "dirty", "head": {"sha": "ghi789"}}

    with patch("src.gate.github_review.get_http_client") as mock_get:
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.put = AsyncMock()  # 호출되면 안 됨 / Must not be called

        result = await merge_pr("token", "owner/repo", 5)

    assert result[0] is False
    assert "dirty" in result[1]
    assert result[2] == "ghi789"
    mock_client.put.assert_not_called()
