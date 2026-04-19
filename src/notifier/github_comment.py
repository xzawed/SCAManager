"""GitHub pull request comment notifier using the GitHub Issues API."""
import httpx

from src.constants import GRADE_EMOJI
from src.github_client.helpers import github_api_headers
from src.scorer.calculator import ScoreResult
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult


def _build_comment_body(
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
) -> str:
    """Build comment by normalizing objects to dict form and delegating to _build_comment_from_result."""
    result = {
        "score": score_result.total,
        "grade": score_result.grade,
        "breakdown": score_result.breakdown,
        "ai_summary": ai_review.summary if ai_review else None,
        "ai_suggestions": ai_review.suggestions if ai_review else [],
        "commit_message_feedback": ai_review.commit_message_feedback if ai_review else None,
        "code_quality_feedback": ai_review.code_quality_feedback if ai_review else None,
        "security_feedback": ai_review.security_feedback if ai_review else None,
        "direction_feedback": ai_review.direction_feedback if ai_review else None,
        "test_feedback": ai_review.test_feedback if ai_review else None,
        "file_feedbacks": ai_review.file_feedbacks if ai_review else [],
        "issues": [
            {"tool": i.tool, "severity": i.severity, "message": i.message, "line": i.line}
            for r in analysis_results
            for i in r.issues
        ],
    }
    return _build_comment_from_result(result)


async def post_pr_comment(  # pylint: disable=too-many-positional-arguments
    github_token: str,
    repo_name: str,
    pr_number: int,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
) -> None:
    """Post a formatted analysis result comment on a GitHub pull request."""
    body = _build_comment_body(score_result, analysis_results, ai_review)
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            json={"body": body},
            headers=github_api_headers(github_token),
        )
        r.raise_for_status()


def _build_comment_from_result(result: dict) -> str:
    """Build a formatted PR comment body from a stored analysis result dict."""
    score = result.get("score", 0)
    grade = result.get("grade", "F")
    breakdown = result.get("breakdown", {})
    grade_emoji = GRADE_EMOJI.get(grade, "⚪")

    lines = [
        f"## {grade_emoji} SCAManager 분석 결과",
        "",
        f"**총점: {score}/100** (등급 {grade})",
        "",
        "### 점수 상세",
        "| 항목 | 점수 | 만점 |",
        "|------|------|------|",
        f"| 커밋 메시지 | {breakdown.get('commit_message', '-')} | 15 |",
        f"| 코드 품질 | {breakdown.get('code_quality', '-')} | 25 |",
        f"| 보안 | {breakdown.get('security', '-')} | 20 |",
        f"| 구현 방향성 (AI) | {breakdown.get('ai_review', '-')} | 25 |",
        f"| 테스트 | {breakdown.get('test_coverage', '-')} | 15 |",
    ]

    if result.get("ai_summary"):
        lines += ["", "### AI 요약", result["ai_summary"]]

    feedback_items = [
        ("커밋 메시지", result.get("commit_message_feedback")),
        ("코드 품질", result.get("code_quality_feedback")),
        ("보안", result.get("security_feedback")),
        ("구현 방향성", result.get("direction_feedback")),
        ("테스트", result.get("test_feedback")),
    ]
    if any(fb for _, fb in feedback_items):
        lines += ["", "### 카테고리별 피드백"]
        for label, fb in feedback_items:
            if fb:
                lines.append(f"- **{label}**: {fb}")

    if result.get("file_feedbacks"):
        lines += ["", "### 파일별 피드백"]
        for ff in result["file_feedbacks"]:
            lines.append(f"#### `{ff.get('file', '?')}`")
            for issue in ff.get("issues", []):
                lines.append(f"- {issue}")

    if result.get("ai_suggestions"):
        lines += ["", "### 개선 제안"]
        for s in result["ai_suggestions"]:
            lines.append(f"- {s}")

    if result.get("issues"):
        lines += ["", "### 정적 분석 이슈 (상위 10건)"]
        for issue in result["issues"][:10]:
            lines.append(
                f"- **[{issue.get('tool', '?')}]** {issue.get('message', '')} "
                f"(line {issue.get('line', '?')})"
            )

    return "\n".join(lines)


async def post_pr_comment_from_result(
    github_token: str,
    repo_name: str,
    pr_number: int,
    result: dict,
) -> None:
    """Post a formatted analysis result comment from a stored result dict."""
    body = _build_comment_from_result(result)
    url = f"https://api.github.com/repos/{repo_name}/issues/{pr_number}/comments"
    async with httpx.AsyncClient() as client:
        r = await client.post(
            url,
            json={"body": body},
            headers=github_api_headers(github_token),
        )
        r.raise_for_status()
