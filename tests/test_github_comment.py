import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.notifier.github_comment import _build_comment_body, post_pr_comment
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult, AnalysisIssue
from src.analyzer.ai_review import AiReviewResult


def _make_score(total=82, grade="B"):
    return ScoreResult(
        total=total, grade=grade,
        code_quality_score=28, security_score=20,
        breakdown={
            "code_quality": 28, "security": 20,
            "commit_message": 17, "ai_review": 15, "test_coverage": 2,
        },
    )


def _make_ai_review():
    return AiReviewResult(
        commit_score=17, ai_score=15, has_tests=True,
        summary="좋은 리팩토링입니다.",
        suggestions=["타입 힌트 추가 권장", "메서드 분리 고려"],
    )


def test_comment_body_contains_total_score():
    body = _build_comment_body(_make_score(), [], None)
    assert "82/100" in body
    assert "등급 B" in body


def test_comment_body_contains_grade_emoji():
    body = _build_comment_body(_make_score(total=82, grade="B"), [], None)
    assert "🔵" in body


def test_comment_body_contains_breakdown_table():
    body = _build_comment_body(_make_score(), [], None)
    assert "커밋 메시지" in body
    assert "코드 품질" in body
    assert "보안" in body
    assert "구현 방향성" in body
    assert "테스트" in body


def test_comment_body_includes_ai_summary_and_suggestions():
    body = _build_comment_body(_make_score(), [], _make_ai_review())
    assert "좋은 리팩토링입니다." in body
    assert "타입 힌트 추가 권장" in body
    assert "메서드 분리 고려" in body


def test_comment_body_includes_static_issues():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="undefined-variable", line=5)]
    r = StaticAnalysisResult(filename="app.py", issues=issues)
    body = _build_comment_body(_make_score(), [r], None)
    assert "undefined-variable" in body
    assert "pylint" in body
    assert "line 5" in body


def test_comment_body_no_issues_section_when_empty():
    body = _build_comment_body(_make_score(), [], None)
    assert "주요 이슈" not in body


def test_comment_body_limits_issues_to_10():
    issues = [
        AnalysisIssue(tool="flake8", severity="warning", message=f"issue-{i}", line=i)
        for i in range(20)
    ]
    r = StaticAnalysisResult(filename="app.py", issues=issues)
    body = _build_comment_body(_make_score(), [r], None)
    assert body.count("flake8") <= 10


async def test_post_pr_comment_calls_github_api():
    with patch("src.notifier.github_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_pr_comment(
            github_token="ghp_test",
            repo_name="owner/repo",
            pr_number=42,
            score_result=_make_score(),
            analysis_results=[],
            ai_review=None,
        )

    mock_client.post.assert_called_once()
    url = mock_client.post.call_args[0][0]
    assert "owner/repo" in url
    assert "42" in url


def test_comment_body_includes_category_feedback():
    ai = AiReviewResult(
        commit_score=17, ai_score=15, has_tests=True,
        summary="좋은 리팩토링입니다.",
        suggestions=["타입 힌트 추가 권장"],
        commit_message_feedback="커밋 메시지가 변경 범위를 잘 설명합니다.",
        code_quality_feedback="전반적으로 깔끔한 코드입니다.",
        security_feedback="보안 이슈가 발견되지 않았습니다.",
        direction_feedback="설계 방향이 적절합니다.",
        test_feedback="테스트 코드가 포함되어 있습니다.",
        file_feedbacks=[{"file": "app.py", "issues": ["라인 10: 변수명 개선 필요"]}],
    )
    body = _build_comment_body(_make_score(), [], ai)
    assert "커밋 메시지가 변경 범위를 잘 설명합니다." in body
    assert "전반적으로 깔끔한 코드입니다." in body
    assert "보안 이슈가 발견되지 않았습니다." in body
    assert "설계 방향이 적절합니다." in body
    assert "테스트 코드가 포함되어 있습니다." in body
    assert "app.py" in body
    assert "변수명 개선 필요" in body


async def test_post_pr_comment_sets_auth_header():
    with patch("src.notifier.github_comment.httpx.AsyncClient") as mock_cls:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=None)

        await post_pr_comment(
            github_token="ghp_test",
            repo_name="owner/repo",
            pr_number=1,
            score_result=_make_score(),
            analysis_results=[],
            ai_review=None,
        )

    headers = mock_client.post.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer ghp_test"
