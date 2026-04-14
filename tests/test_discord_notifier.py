import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.discord import send_discord_notification, _build_embed
from src.constants import GRADE_COLOR_DISCORD as GRADE_COLORS
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


def test_build_embed_contains_repo_and_score():
    embed = _build_embed("owner/repo", "abc1234", _make_score(82, "B"), _make_analysis(), None)
    assert "owner/repo" in embed["title"]
    assert "82" in embed["description"]
    assert "B" in embed["description"]


def test_build_embed_color_matches_grade():
    for grade, expected_color in GRADE_COLORS.items():
        embed = _build_embed("r", "sha", _make_score(grade=grade), _make_analysis(), None)
        assert embed["color"] == expected_color


def test_build_embed_includes_breakdown_fields():
    embed = _build_embed("owner/repo", "abc1234", _make_score(), _make_analysis(), None)
    field_names = [f["name"] for f in embed["fields"]]
    assert "코드 품질" in field_names
    assert "보안" in field_names
    assert "커밋 메시지" in field_names
    assert "구현 방향성" in field_names
    assert "테스트" in field_names


def test_build_embed_shows_pr_number():
    embed = _build_embed("owner/repo", "abc1234", _make_score(), _make_analysis(), pr_number=42)
    assert "PR #42" in embed["title"] or "PR #42" in embed["description"]


def test_build_embed_shows_commit_when_no_pr():
    embed = _build_embed("owner/repo", "abc1234567", _make_score(), _make_analysis(), None)
    assert "abc1234" in embed["description"]


def test_build_embed_includes_ai_summary():
    ai = AiReviewResult(
        commit_score=17, ai_score=15, test_score=10,
        summary="좋은 리팩토링입니다.",
        suggestions=["타입 힌트를 추가하세요"],
    )
    embed = _build_embed("owner/repo", "abc1234", _make_score(), _make_analysis(), None, ai_review=ai)
    desc = embed["description"]
    assert "좋은 리팩토링입니다." in desc


def test_build_embed_includes_issues():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="undefined variable x", line=5)]
    embed = _build_embed("owner/repo", "abc1234", _make_score(), _make_analysis(issues), None)
    desc = embed["description"]
    assert "undefined variable x" in desc


def test_build_embed_truncates_long_description():
    """Discord embed description 상한(4096자) 적용."""
    ai = AiReviewResult(
        commit_score=17, ai_score=15, test_score=10,
        summary="A" * 5000,
        suggestions=[],
    )
    embed = _build_embed("owner/repo", "abc1234", _make_score(), _make_analysis(), None, ai_review=ai)
    assert len(embed["description"]) <= 4096


async def test_send_discord_notification_posts_to_webhook():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_post = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=MagicMock(post=mock_post))
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.notifier.discord.validate_external_url", return_value=True), \
         patch("src.notifier.discord.build_safe_client", return_value=mock_client):
        await send_discord_notification(
            webhook_url="https://discord.com/api/webhooks/test",
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
        )

    mock_post.assert_called_once()
    url = mock_post.call_args[0][0]
    assert "discord.com" in url
    payload = mock_post.call_args[1]["json"]
    assert "embeds" in payload
    assert len(payload["embeds"]) == 1


async def test_send_discord_notification_skips_when_no_url():
    """webhook_url이 None이면 아무것도 하지 않는다."""
    with patch("src.notifier.discord.build_safe_client") as mock_build:
        await send_discord_notification(
            webhook_url=None,
            repo_name="owner/repo",
            commit_sha="abc1234",
            score_result=_make_score(),
            analysis_results=_make_analysis(),
        )
    mock_build.assert_not_called()
