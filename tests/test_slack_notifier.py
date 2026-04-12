import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.slack import send_slack_notification, _build_payload
from src.constants import GRADE_COLOR_HTML as GRADE_COLORS
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


def test_build_payload_contains_score_and_repo():
    payload = _build_payload("owner/repo", "abc1234", _make_score(82, "B"), _make_analysis(), None)
    assert "owner/repo" in payload["text"]
    assert "82" in payload["attachments"][0]["pretext"]


def test_build_payload_has_attachments_with_grade_color():
    payload = _build_payload("owner/repo", "abc1234", _make_score(82, "B"), _make_analysis(), None)
    assert "attachments" in payload
    assert payload["attachments"][0]["color"] == GRADE_COLORS["B"]


def test_build_payload_includes_breakdown_fields():
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    fields = payload["attachments"][0]["fields"]
    field_titles = [f["title"] for f in fields]
    assert "코드 품질" in field_titles
    assert "보안" in field_titles
    assert "커밋 메시지" in field_titles
    assert "구현 방향성" in field_titles
    assert "테스트" in field_titles


def test_build_payload_shows_pr_number():
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), pr_number=42)
    assert "PR #42" in payload["text"]


def test_build_payload_shows_commit_when_no_pr():
    payload = _build_payload("owner/repo", "abc1234567", _make_score(), _make_analysis(), None)
    assert "abc1234" in payload["text"]


def test_build_payload_includes_ai_summary():
    ai = AiReviewResult(
        commit_score=17, ai_score=15, test_score=10,
        summary="좋은 리팩토링입니다.",
        suggestions=["타입 힌트를 추가하세요"],
    )
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), None, ai_review=ai)
    attachment_text = payload["attachments"][0].get("text", "")
    assert "좋은 리팩토링입니다." in attachment_text


def test_build_payload_includes_issues():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="undefined variable x", line=5)]
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(issues), None)
    attachment_text = payload["attachments"][0].get("text", "")
    assert "undefined variable x" in attachment_text


async def test_send_slack_notification_posts_to_webhook():
    with patch("src.notifier.slack.httpx.AsyncClient") as MockClient:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post = AsyncMock(return_value=mock_response)
        MockClient.return_value.__aenter__ = AsyncMock(return_value=MagicMock(post=mock_post))
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        await send_slack_notification(
            webhook_url="https://hooks.slack.com/services/T/B/xxx",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
        )

    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    assert "hooks.slack.com" in url


async def test_send_slack_notification_skips_when_no_url():
    with patch("src.notifier.slack.httpx.AsyncClient") as MockClient:
        await send_slack_notification(
            webhook_url=None,
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
        )
    MockClient.assert_not_called()
