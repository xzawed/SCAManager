"""tests/unit/notifier/test_merge_failure_issue.py"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch


def _mock_resp(status_code: int, json_data: dict):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


async def test_create_merge_failure_issue_success():
    """중복 없으면 Issue 생성 후 Issue number 반환."""
    from src.notifier.merge_failure_issue import create_merge_failure_issue
    search_resp = _mock_resp(200, {"total_count": 0})
    create_resp = _mock_resp(201, {"number": 42})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)
    mock_client.post = AsyncMock(return_value=create_resp)

    with patch("src.notifier.merge_failure_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_merge_failure_issue(
            github_token="tok",
            repo_name="owner/repo",
            pr_number=7,
            score=60,
            threshold=75,
            reason="branch_protection_blocked: 머지 조건 미충족",
            advice="Branch Protection 확인 필요",
        )

    assert result == 42
    mock_client.post.assert_called_once()


async def test_create_merge_failure_issue_dedup_skip():
    """24h 내 동일 PR Issue 이미 있으면 None 반환, POST 미호출."""
    from src.notifier.merge_failure_issue import create_merge_failure_issue
    search_resp = _mock_resp(200, {"total_count": 1})

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=search_resp)

    with patch("src.notifier.merge_failure_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_merge_failure_issue(
            github_token="tok",
            repo_name="owner/repo",
            pr_number=7,
            score=60,
            threshold=75,
            reason="branch_protection_blocked: 머지 조건 미충족",
            advice="Branch Protection 확인 필요",
        )

    assert result is None
    mock_client.post.assert_not_called()


async def test_create_merge_failure_issue_http_error_returns_none():
    """네트워크 오류 시 None 반환 (파이프라인 미중단)."""
    from src.notifier.merge_failure_issue import create_merge_failure_issue

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.NetworkError("연결 실패"))

    with patch("src.notifier.merge_failure_issue.httpx.AsyncClient") as mock_cls:
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await create_merge_failure_issue(
            github_token="tok",
            repo_name="owner/repo",
            pr_number=7,
            score=60,
            threshold=75,
            reason="network_error: 연결 실패",
            advice="잠시 후 재시도하세요",
        )

    assert result is None
