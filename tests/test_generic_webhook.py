from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.webhook import send_webhook_notification, _build_payload
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


def test_payload_contains_event_type():
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert payload["event"] == "analysis_complete"


def test_payload_contains_score_breakdown():
    payload = _build_payload("owner/repo", "abc1234", _make_score(82, "B"), _make_analysis(), None)
    assert payload["score"]["total"] == 82
    assert payload["score"]["grade"] == "B"
    assert payload["score"]["breakdown"]["code_quality"] == 22


def test_payload_contains_pr_number():
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), pr_number=42)
    assert payload["pr_number"] == 42


def test_payload_contains_issues_count():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="err", line=1)]
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(issues), None)
    assert payload["issues_count"] == 1


def test_payload_contains_ai_summary():
    ai = AiReviewResult(commit_score=17, ai_score=15, test_score=10,
                        summary="좋은 코드입니다.", suggestions=["힌트 추가"])
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), None, ai_review=ai)
    assert payload["ai_summary"] == "좋은 코드입니다."
    assert payload["ai_suggestions"] == ["힌트 추가"]


def test_payload_ai_fields_empty_when_no_review():
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert payload["ai_summary"] == ""
    assert payload["ai_suggestions"] == []


def test_payload_contains_timestamp():
    payload = _build_payload("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    assert "timestamp" in payload


async def test_send_webhook_posts_to_url():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=MagicMock(post=mock_post))
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.notifier.webhook.validate_external_url", return_value=True), \
         patch("src.notifier.webhook.build_safe_client", return_value=mock_client):
        await send_webhook_notification(
            webhook_url="https://example.com/hook",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
        )

    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]
    assert payload["event"] == "analysis_complete"


async def test_send_webhook_skips_when_no_url():
    with patch("src.notifier.webhook.build_safe_client") as mock_build:
        await send_webhook_notification(
            webhook_url=None,
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
        )
    mock_build.assert_not_called()
