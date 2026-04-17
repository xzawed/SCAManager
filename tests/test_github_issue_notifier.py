"""Tests for src/notifier/github_issue.py — create_low_score_issue()."""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("APP_BASE_URL", "https://scamanager.example.com")

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest


def _make_result(score=35, with_security_high=False):
    issues = []
    if with_security_high:
        issues.append({
            "tool": "bandit", "severity": "HIGH",
            "message": "B602: subprocess with shell=True", "line": 10,
        })
    return {
        "source": "push",
        "score": score,
        "grade": "F" if score < 45 else "D",
        "ai_summary": "보안 문제가 여러 건 발견되었습니다.",
        "ai_suggestions": ["입력값 검증 추가"],
        "issues": issues,
    }


def _mock_httpx_post(status=201, number=42):
    """Returns a patch context manager for httpx.AsyncClient that captures POST calls."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = status
    mock_response.json = MagicMock(return_value={"number": number, "html_url": f"https://github.com/x/y/issues/{number}"})
    mock_response.raise_for_status = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


async def test_create_low_score_issue_success():
    from src.notifier.github_issue import create_low_score_issue
    with patch("src.notifier.github_issue.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_httpx_post(number=42)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        number = await create_low_score_issue(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc123def456",
            analysis_id=99,
            result=_make_result(score=35),
        )

    assert number == 42
    mock_client.post.assert_called_once()
    url = mock_client.post.call_args[0][0]
    assert url == "https://api.github.com/repos/owner/repo/issues"


async def test_create_low_score_issue_title_format():
    from src.notifier.github_issue import create_low_score_issue
    with patch("src.notifier.github_issue.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_httpx_post()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await create_low_score_issue(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc123def456",
            analysis_id=1,
            result=_make_result(score=35),
        )

    body = mock_client.post.call_args[1]["json"]
    assert "abc123d" in body["title"]
    assert "35" in body["title"]
    assert "SCAManager" in body["title"]


async def test_create_low_score_issue_body_has_analysis_link():
    from src.notifier.github_issue import create_low_score_issue
    with patch("src.notifier.github_issue.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_httpx_post()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await create_low_score_issue(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc123def456",
            analysis_id=99,
            result=_make_result(score=35),
        )

    body = mock_client.post.call_args[1]["json"]
    assert "/repos/owner/repo/analyses/99" in body["body"]


async def test_create_low_score_issue_labels_default():
    from src.notifier.github_issue import create_low_score_issue
    with patch("src.notifier.github_issue.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_httpx_post()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await create_low_score_issue(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            analysis_id=1,
            result=_make_result(score=35, with_security_high=False),
        )

    body = mock_client.post.call_args[1]["json"]
    assert "scamanager" in body["labels"]
    assert "code-quality" in body["labels"]
    assert "security" not in body["labels"]


async def test_create_low_score_issue_security_label_when_high():
    from src.notifier.github_issue import create_low_score_issue
    with patch("src.notifier.github_issue.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_httpx_post()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await create_low_score_issue(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            analysis_id=1,
            result=_make_result(score=80, with_security_high=True),
        )

    body = mock_client.post.call_args[1]["json"]
    assert "security" in body["labels"]


async def test_create_low_score_issue_auth_header():
    from src.notifier.github_issue import create_low_score_issue
    with patch("src.notifier.github_issue.httpx.AsyncClient") as mock_cls:
        mock_client = _mock_httpx_post()
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await create_low_score_issue(
            github_token="ghp_MY_TOKEN",
            repo_name="owner/repo",
            commit_sha="abc",
            analysis_id=1,
            result=_make_result(),
        )

    headers = mock_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ghp_MY_TOKEN"


async def test_create_low_score_issue_httpx_error_returns_none():
    from src.notifier.github_issue import create_low_score_issue
    with patch("src.notifier.github_issue.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("boom"))
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        number = await create_low_score_issue(
            github_token="ghp_test",
            repo_name="owner/repo",
            commit_sha="abc",
            analysis_id=1,
            result=_make_result(),
        )

    assert number is None


async def test_create_low_score_issue_keyword_only():
    """Positional 호출 시 TypeError가 발생해야 한다 (keyword-only 강제)."""
    from src.notifier.github_issue import create_low_score_issue
    with pytest.raises(TypeError):
        await create_low_score_issue(
            "ghp_test", "owner/repo", "abc", 1, _make_result()
        )
