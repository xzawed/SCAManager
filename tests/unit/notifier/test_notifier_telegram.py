import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.notifier.telegram import send_analysis_result, _build_message
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult, AnalysisIssue
from src.analyzer.io.ai_review import AiReviewResult


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


def test_build_message_includes_ai_summary():
    ai = AiReviewResult(
        commit_score=17, ai_score=15, test_score=10,
        summary="전체적으로 좋은 리팩토링입니다.",
        suggestions=["타입 힌트를 추가하세요", "함수를 분리하세요"],
    )
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(), None, ai_review=ai)
    assert "전체적으로 좋은 리팩토링입니다." in msg
    assert "타입 힌트를 추가하세요" in msg
    assert "함수를 분리하세요" in msg


def test_build_message_escapes_html_special_chars():
    """HTML 특수문자가 이스케이프되어 Telegram 파싱 오류를 방지해야 한다."""
    ai = AiReviewResult(
        commit_score=17, ai_score=15, test_score=10,
        summary="변수 <user_name>을 사용하세요 & 'config'를 확인",
        suggestions=["func<T>() 제네릭을 추가하세요"],
    )
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(), None, ai_review=ai)
    assert "&lt;user_name&gt;" in msg
    assert "&amp;" in msg
    assert "<user_name>" not in msg


def test_build_message_escapes_issue_text():
    """정적 분석 이슈 메시지의 특수문자도 이스케이프되어야 한다."""
    issues = [AnalysisIssue(tool="pylint", severity="error", message="Unable to import 'src.config'", line=1)]
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(issues), None)
    assert "Unable to import &#x27;src.config&#x27;" in msg or "Unable to import 'src.config'" in msg
    assert "[pylint]" in msg


def test_build_message_uses_html_formatting():
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert "<b>" in msg
    assert "<code>" in msg


def test_build_message_includes_score_breakdown():
    msg = _build_message("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert "코드 품질" in msg
    assert "보안" in msg
    assert "커밋" in msg


@pytest.mark.asyncio
async def test_send_analysis_result_uses_html_parse_mode():
    with patch("src.notifier.telegram.get_http_client") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_get.return_value = mock_client
        mock_post = AsyncMock(return_value=mock_response)
        mock_client.post = mock_post

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
    assert call_kwargs["json"]["parse_mode"] == "HTML"
