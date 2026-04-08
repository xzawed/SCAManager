from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.email import send_email_notification, _build_html_body
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult, AnalysisIssue
from src.analyzer.ai_review import AiReviewResult


def _make_score(total=82, grade="B"):
    return ScoreResult(
        total=total, grade=grade,
        code_quality_score=22, security_score=18,
        breakdown={
            "code_quality": 22, "security": 18,
            "commit_message": 14, "ai_review": 21, "test_coverage": 7,
        },
    )


def _make_analysis(issues=None) -> list[StaticAnalysisResult]:
    r = StaticAnalysisResult(filename="app.py")
    r.issues = issues or []
    return [r]


def test_build_html_contains_score():
    html = _build_html_body("owner/repo", "abc1234", _make_score(82, "B"), _make_analysis(), None)
    assert "82" in html
    assert "B" in html


def test_build_html_contains_repo_name():
    html = _build_html_body("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert "owner/repo" in html


def test_build_html_contains_breakdown():
    html = _build_html_body("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert "코드 품질" in html
    assert "보안" in html
    assert "테스트" in html


def test_build_html_contains_pr_number():
    html = _build_html_body("owner/repo", "abc1234", _make_score(), _make_analysis(), pr_number=42)
    assert "PR #42" in html


def test_build_html_includes_ai_summary():
    ai = AiReviewResult(commit_score=17, ai_score=15, test_score=10,
                        summary="좋은 리팩토링입니다.", suggestions=[])
    html = _build_html_body("owner/repo", "abc1234", _make_score(), _make_analysis(), None, ai_review=ai)
    assert "좋은 리팩토링입니다." in html


def test_build_html_includes_issues():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="undefined var", line=5)]
    html = _build_html_body("owner/repo", "abc1234", _make_score(), _make_analysis(issues), None)
    assert "undefined var" in html


async def test_send_email_skips_when_no_recipients():
    """수신자가 없으면 아무것도 하지 않는다."""
    with patch("src.notifier.email.aiosmtplib") as mock_smtp:
        await send_email_notification(
            recipients=None,
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
        )
    mock_smtp.send.assert_not_called()


async def test_send_email_skips_when_no_smtp_config():
    """SMTP 설정이 없으면 아무것도 하지 않는다."""
    with patch("src.notifier.email.aiosmtplib") as mock_smtp:
        await send_email_notification(
            recipients="test@example.com",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
            smtp_host=None,
        )
    mock_smtp.send.assert_not_called()


async def test_send_email_calls_smtp():
    """SMTP 설정과 수신자가 있으면 이메일을 발송한다."""
    with patch("src.notifier.email.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock()

        await send_email_notification(
            recipients="a@test.com, b@test.com",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_user="user",
            smtp_pass="pass",
        )

    mock_smtp.send.assert_called_once()
    msg = mock_smtp.send.call_args[0][0]
    assert "a@test.com" in msg["To"]
    assert "b@test.com" in msg["To"]
    assert "SCA" in msg["Subject"]
