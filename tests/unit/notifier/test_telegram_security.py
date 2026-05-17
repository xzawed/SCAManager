"""Telegram HTML injection 방어 단위 테스트.
Unit tests for HTML injection defense in _build_message().

src/notifier/telegram.py::_build_message() 의 html.escape() 적용 여부 검증.
Verifies html.escape() is applied to user-controlled fields in _build_message().
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-cid")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-csecret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

from unittest.mock import MagicMock, patch

from src.notifier.telegram import _build_message


def _make_score_result(total: int = 85, grade: str = "B") -> MagicMock:
    """기본 ScoreResult mock 생성 헬퍼.
    Helper to build a basic ScoreResult mock.
    """
    return MagicMock(
        total=total,
        grade=grade,
        breakdown={
            "commit_message": 20,
            "code_quality": 20,
            "security": 20,
            "ai_review": 15,
            "test_coverage": 10,
        },
    )


def _make_ai_review(summary: str = "OK", suggestions: list[str] | None = None) -> MagicMock:
    """기본 AiReviewResult mock 생성 헬퍼.
    Helper to build a basic AiReviewResult mock.
    """
    return MagicMock(summary=summary, suggestions=suggestions or [])


def _make_issue(tool: str = "pylint", message: str = "W0001 some issue") -> MagicMock:
    """단일 이슈 mock 생성 헬퍼.
    Helper to build a single issue mock.
    """
    return MagicMock(tool=tool, message=message)


# get_text를 단순화 — 키워드 인자를 str()로 반환해 이스케이프 결과가 output에 포함되도록 함
# Simplify get_text — returns str(kwargs) so escaped content appears in output
_FAKE_GET_TEXT = lambda key, lang, **kw: " ".join(str(v) for v in kw.values())


def test_repo_name_with_html_is_escaped():
    """repo_name에 <script> 포함 시 출력에 리터럴 <script>가 없고 &lt;script&gt;가 있어야 함.
    When repo_name contains <script>, output must not contain literal <script>
    and must contain &lt;script&gt;.
    """
    malicious_repo = "<script>alert(1)</script>/repo"
    score = _make_score_result()
    ai_review = _make_ai_review()

    with patch("src.notifier.telegram.get_text", side_effect=_FAKE_GET_TEXT), \
         patch("src.notifier.telegram.get_all_issues", return_value=[]):
        result = _build_message(
            repo_name=malicious_repo,
            commit_sha="abc1234",
            score_result=score,
            analysis_results=[],
            pr_number=None,
            ai_review=ai_review,
        )

    # 리터럴 HTML 태그가 출력에 포함되면 안 됨
    # Literal HTML tag must not appear in the output
    assert "<script>" not in result
    # 이스케이프된 형태가 포함되어야 함
    # Escaped form must appear
    assert "&lt;script&gt;" in result


def test_ai_summary_with_html_is_escaped():
    """ai_review.summary에 <b>xss</b> 포함 시 이스케이프되어 출력되어야 함.
    When ai_review.summary contains <b>xss</b>, output must have escaped form.
    """
    malicious_summary = "<b>xss</b>"
    score = _make_score_result()
    ai_review = _make_ai_review(summary=malicious_summary)

    with patch("src.notifier.telegram.get_text", side_effect=_FAKE_GET_TEXT), \
         patch("src.notifier.telegram.get_all_issues", return_value=[]):
        result = _build_message(
            repo_name="safe/repo",
            commit_sha="abc1234",
            score_result=score,
            analysis_results=[],
            pr_number=None,
            ai_review=ai_review,
        )

    # 리터럴 <b> 태그가 출력에 포함되면 안 됨
    # Literal <b> tag must not appear in the output
    assert "<b>xss</b>" not in result
    # 이스케이프된 형태가 포함되어야 함
    # Escaped form must appear
    assert "&lt;b&gt;xss&lt;/b&gt;" in result


def test_ai_suggestion_with_html_is_escaped():
    """ai_review.suggestions 항목에 <img src=x onerror=alert(1)> 포함 시 이스케이프되어야 함.
    When ai_review.suggestions contain an img tag with onerror, output must be escaped.
    """
    malicious_suggestion = "<img src=x onerror=alert(1)>"
    score = _make_score_result()
    ai_review = _make_ai_review(suggestions=[malicious_suggestion])

    with patch("src.notifier.telegram.get_text", side_effect=_FAKE_GET_TEXT), \
         patch("src.notifier.telegram.get_all_issues", return_value=[]):
        result = _build_message(
            repo_name="safe/repo",
            commit_sha="abc1234",
            score_result=score,
            analysis_results=[],
            pr_number=None,
            ai_review=ai_review,
        )

    # 리터럴 <img> 여는 태그가 출력에 포함되면 안 됨 — 이스케이프 대상
    # Literal <img opening tag must not appear — it is an escape target
    assert "<img" not in result
    # 닫는 > 도 이스케이프되어 &gt; 형태여야 함
    # The closing > must also be escaped as &gt;
    assert "onerror=alert(1)>" not in result
    # 이스케이프된 여는 태그 형태가 포함되어야 함
    # Escaped opening tag form must appear
    assert "&lt;img" in result
    # 이스케이프된 닫는 꺽쇠 형태가 포함되어야 함
    # Escaped closing angle bracket must appear
    assert "alert(1)&gt;" in result


def test_issue_message_with_html_is_escaped():
    """issue.message에 <script>alert(1)</script> 포함 시 이스케이프되어 출력되어야 함.
    When issue.message contains a script tag, output must be escaped.
    """
    malicious_message = "<script>alert(1)</script>"
    mock_issue = _make_issue(tool="bandit", message=malicious_message)
    score = _make_score_result()
    ai_review = _make_ai_review()

    with patch("src.notifier.telegram.get_text", side_effect=_FAKE_GET_TEXT), \
         patch("src.notifier.telegram.get_all_issues", return_value=[mock_issue]):
        result = _build_message(
            repo_name="safe/repo",
            commit_sha="abc1234",
            score_result=score,
            analysis_results=[],
            pr_number=None,
            ai_review=ai_review,
        )

    # 리터럴 <script> 태그가 출력에 포함되면 안 됨
    # Literal <script> tag must not appear in the output
    assert "<script>" not in result
    # 이스케이프된 형태가 포함되어야 함
    # Escaped form must appear
    assert "&lt;script&gt;" in result
