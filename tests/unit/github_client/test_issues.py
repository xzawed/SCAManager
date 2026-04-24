"""tests/test_github_client_issues.py

src/github_client/issues.py (미구현) 에 대한 선작성 테스트.
구현 파일이 없으므로 pytest collect 시 ImportError → ERRORS 표시 = 정상 Red 상태.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from src.github_client.issues import close_issue  # 구현 전 → ImportError (Red)
from src.github_client.helpers import github_api_headers


# ---------------------------------------------------------------------------
# 테스트 1: PATCH 요청이 올바른 URL과 body로 전송되는지 확인
# ---------------------------------------------------------------------------
async def test_close_issue_sends_patch_with_state_closed():
    """close_issue() 호출 시 GitHub Issues API에 state=closed PATCH 요청이 전송된다."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.patch = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.github_client.issues.get_http_client", return_value=mock_client):
        await close_issue("token", "owner/repo", 42)

    mock_client.patch.assert_called_once()
    call_kwargs = mock_client.patch.call_args

    # 첫 번째 위치 인자 = URL
    called_url = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("url")
    assert called_url == "https://api.github.com/repos/owner/repo/issues/42"

    # json 바디에 state=closed, state_reason=completed 포함
    called_json = call_kwargs.kwargs.get("json") or {}
    assert called_json.get("state") == "closed"
    assert called_json.get("state_reason") == "completed"


# ---------------------------------------------------------------------------
# 테스트 2: github_api_headers() 헬퍼의 Authorization 헤더가 요청에 포함된다
# ---------------------------------------------------------------------------
async def test_close_issue_uses_bearer_token_via_helper():
    """close_issue()가 github_api_headers()를 통해 Bearer 인증 헤더를 전송한다."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.patch = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.github_client.issues.get_http_client", return_value=mock_client):
        await close_issue("mytoken", "owner/repo", 7)

    call_kwargs = mock_client.patch.call_args
    called_headers = call_kwargs.kwargs.get("headers") or {}

    expected_headers = github_api_headers("mytoken")
    # Authorization: Bearer mytoken 헤더가 전달된 헤더와 일치해야 한다
    assert called_headers.get("Authorization") == expected_headers["Authorization"]
    assert called_headers.get("Authorization") == "Bearer mytoken"


# ---------------------------------------------------------------------------
# 테스트 3: 서버 4xx/5xx 응답 시 HTTPStatusError가 propagation된다
# ---------------------------------------------------------------------------
async def test_close_issue_http_error_raises():
    """GitHub API가 422를 반환하면 httpx.HTTPStatusError가 호출자로 전파된다."""
    mock_response = MagicMock()
    # raise_for_status()가 HTTPStatusError를 발생시키도록 설정
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "422 Unprocessable Entity",
            request=MagicMock(),
            response=MagicMock(status_code=422),
        )
    )

    mock_client = AsyncMock()
    mock_client.patch = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("src.github_client.issues.get_http_client", return_value=mock_client):
        with pytest.raises(httpx.HTTPStatusError):
            await close_issue("token", "owner/repo", 99)
