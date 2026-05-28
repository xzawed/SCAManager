# tests/unit/github_client/test_issues_create.py
from unittest.mock import AsyncMock, MagicMock
import pytest
from src.github_client.issues import create_issue, get_issue_state


def _mock_client(monkeypatch, json_data):
    """get_http_client() 싱글톤을 모킹한다.
    Mock the get_http_client() singleton.
    """
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock(return_value=None)
    mock_response.json.return_value = json_data
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("src.github_client.issues.get_http_client", lambda: mock_client)
    return mock_client


@pytest.mark.asyncio
async def test_create_issue_returns_number_url_state(monkeypatch):
    _mock_client(monkeypatch, {
        "number": 44,
        "html_url": "https://github.com/owner/repo/issues/44",
        "state": "open",
    })
    result = await create_issue(
        "token", "owner/repo",
        title="Test", body="Body", labels=["bug"],
    )
    assert result["number"] == 44
    assert result["html_url"] == "https://github.com/owner/repo/issues/44"
    assert result["state"] == "open"


@pytest.mark.asyncio
async def test_create_issue_sends_correct_payload(monkeypatch):
    mock_client = _mock_client(monkeypatch, {
        "number": 1, "html_url": "https://github.com/o/r/issues/1", "state": "open"
    })
    await create_issue("token", "owner/repo", title="T", body="B", labels=["l1", "l2"])
    call_kwargs = mock_client.post.call_args.kwargs
    assert call_kwargs["json"] == {"title": "T", "body": "B", "labels": ["l1", "l2"]}


@pytest.mark.asyncio
async def test_get_issue_state_returns_open(monkeypatch):
    _mock_client(monkeypatch, {"state": "open"})
    state = await get_issue_state("token", "owner/repo", 44)
    assert state == "open"


@pytest.mark.asyncio
async def test_get_issue_state_returns_closed(monkeypatch):
    _mock_client(monkeypatch, {"state": "closed"})
    state = await get_issue_state("token", "owner/repo", 44)
    assert state == "closed"
