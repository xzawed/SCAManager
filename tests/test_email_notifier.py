from unittest.mock import AsyncMock, MagicMock, patch

import aiosmtplib
import pytest

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


# ---------------------------------------------------------------------------
# SMTP 에러 엣지 케이스
# ---------------------------------------------------------------------------

async def test_send_email_smtp_connect_error_propagates():
    """SMTP 연결 실패(SMTPConnectError)는 예외로 전파된다(미처리 문서화)."""
    with patch("src.notifier.email.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock(
            side_effect=aiosmtplib.SMTPConnectError("Connection refused")
        )
        with pytest.raises(aiosmtplib.SMTPConnectError):
            await send_email_notification(
                recipients="a@test.com",
                repo_name="owner/repo",
                commit_sha="abc1234",
                score_result=_make_score(),
                analysis_results=_make_analysis(),
                smtp_host="smtp.test.com",
            )


async def test_send_email_smtp_auth_error_propagates():
    """SMTP 인증 실패(SMTPAuthenticationError)는 예외로 전파된다."""
    with patch("src.notifier.email.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock(
            side_effect=aiosmtplib.SMTPAuthenticationError(535, "Authentication failed")
        )
        with pytest.raises(aiosmtplib.SMTPAuthenticationError):
            await send_email_notification(
                recipients="a@test.com",
                repo_name="owner/repo",
                commit_sha="abc1234",
                score_result=_make_score(),
                analysis_results=_make_analysis(),
                smtp_host="smtp.test.com",
                smtp_user="bad_user",
                smtp_pass="bad_pass",
            )


async def test_send_email_from_defaults_to_localhost_when_no_user():
    """smtp_user=None 이면 From 헤더가 'sca@localhost'로 설정된다."""
    with patch("src.notifier.email.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock()
        await send_email_notification(
            recipients="a@test.com",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
            smtp_host="smtp.test.com",
            smtp_user=None,
        )
    msg = mock_smtp.send.call_args[0][0]
    assert msg["From"] == "sca@localhost"


async def test_send_email_subject_contains_score_and_grade():
    """Subject 헤더에 점수와 등급이 포함된다."""
    with patch("src.notifier.email.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock()
        await send_email_notification(
            recipients="a@test.com",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(total=91, grade="A"),
            analysis_results=_make_analysis(),
            smtp_host="smtp.test.com",
        )
    msg = mock_smtp.send.call_args[0][0]
    assert "91" in msg["Subject"]
    assert "A" in msg["Subject"]
