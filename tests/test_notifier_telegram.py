import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.notifier.telegram import send_analysis_result, _build_message
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult, AnalysisIssue


def _make_score(total=80, grade="B") -> ScoreResult:
    return ScoreResult(
        total=total, grade=grade,
        code_quality_score=25, security_score=20,
        breakdown={"code_quality": 25, "security": 20, "commit_message": 15, "ai_review": 15, "test_coverage": 5},
    )


def _make_analysis(issues=None) -> list[StaticAnalysisResult]:
    r = StaticAnalysisResult(filename="app.py")
    r.issues = issues or []
    return [r]


def test_build_message_contains_repo_name():
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert "owner/repo" in msg

def test_build_message_contains_score():
    msg = _build_message("owner/repo", "abc1234", _make_score(80, "B"), _make_analysis(), None)
    assert "80" in msg
    assert "B" in msg

def test_build_message_shows_pr_number():
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(), 42)
    assert "PR #42" in msg

def test_build_message_shows_commit_when_no_pr():
    msg = _build_message("owner/repo", "abc1234567", _make_score(), _make_analysis(), None)
    assert "abc1234" in msg

def test_build_message_lists_issues():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="undefined variable x", line=5)]
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(issues), None)
    assert "undefined variable x" in msg

@pytest.mark.asyncio
async def test_send_analysis_result_calls_telegram_api():
    with patch("src.notifier.telegram.httpx.AsyncClient") as MockClient:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=mock_post))
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        await send_analysis_result(
            bot_token="123:ABC",
            chat_id="-100123",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
            pr_number=None,
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args[1]
    assert "sendMessage" in mock_post.call_args[0][0]
    assert call_kwargs["json"]["chat_id"] == "-100123"
