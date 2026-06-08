"""GitHub pull request comment notifier using the GitHub Issues API.

Phase 3 PR-11 (사이클 84) — i18n: language 인자 + 3-layer fallback (resolve_notification_language).
Phase 3 PR-11 (Cycle 84) — i18n: language arg + 3-layer fallback.
"""
from src.constants import GITHUB_API, GRADE_EMOJI, NOTIFIER_MAX_ISSUES_LONG
from src.github_client.helpers import github_api_headers
from src.i18n.loader import get_text
from src.notifier._common import resolve_ai_summary
from src.shared.http_client import get_http_client
from src.scorer.calculator import ScoreResult
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult


def _build_comment_body(
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
    language: str = "en",
) -> str:
    """Build comment by normalizing objects to dict form and delegating to _build_comment_from_result."""
    result = {
        "score": score_result.total,
        "grade": score_result.grade,
        "breakdown": score_result.breakdown,
        "ai_summary": resolve_ai_summary(ai_review, language),
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
    return _build_comment_from_result(result, language=language)


async def post_pr_comment(  # pylint: disable=too-many-positional-arguments
    github_token: str,
    repo_name: str,
    pr_number: int,
    score_result: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
    language: str = "en",
) -> None:
    """Post a formatted analysis result comment on a GitHub pull request (Phase 3 PR-11 — i18n)."""
    body = _build_comment_body(score_result, analysis_results, ai_review, language=language)
    url = f"{GITHUB_API}/repos/{repo_name}/issues/{pr_number}/comments"
    client = get_http_client()
    r = await client.post(
        url,
        json={"body": body},
        headers=github_api_headers(github_token),
    )
    r.raise_for_status()


def _header_lines(result: dict, language: str = "en") -> list[str]:
    """헤더(등급/총점/점수표) 라인 생성."""
    score = result.get("score", 0)
    grade = result.get("grade", "F")
    breakdown = result.get("breakdown", {})
    grade_emoji = GRADE_EMOJI.get(grade, "⚪")
    return [
        get_text("notifier.github_pr_comment.title", language, emoji=grade_emoji),
        "",
        get_text("notifier.github_pr_comment.total_line", language, score=score, grade=grade),
        "",
        get_text("notifier.github_pr_comment.breakdown_header", language),
        get_text("notifier.github_pr_comment.table_header", language),
        get_text("notifier.github_pr_comment.table_separator", language),
        get_text("notifier.github_pr_comment.row_commit", language, value=breakdown.get("commit_message", "-")),
        get_text("notifier.github_pr_comment.row_quality", language, value=breakdown.get("code_quality", "-")),
        get_text("notifier.github_pr_comment.row_security", language, value=breakdown.get("security", "-")),
        get_text("notifier.github_pr_comment.row_direction", language, value=breakdown.get("ai_review", "-")),
        get_text("notifier.github_pr_comment.row_test", language, value=breakdown.get("test_coverage", "-")),
    ]


def _ai_summary_lines(result: dict, language: str = "en") -> list[str]:
    """AI 요약 섹션."""
    if not result.get("ai_summary"):
        return []
    return [
        "",
        get_text("notifier.github_pr_comment.ai_summary_header", language),
        result["ai_summary"],
    ]


def _category_feedback_lines(result: dict, language: str = "en") -> list[str]:
    """카테고리별 피드백 섹션. 전체 피드백이 비어있으면 빈 목록."""
    feedback_items = [
        (get_text("notifier.github_pr_comment.category_commit", language), result.get("commit_message_feedback")),
        (get_text("notifier.github_pr_comment.category_quality", language), result.get("code_quality_feedback")),
        (get_text("notifier.github_pr_comment.category_security", language), result.get("security_feedback")),
        (get_text("notifier.github_pr_comment.category_direction", language), result.get("direction_feedback")),
        (get_text("notifier.github_pr_comment.category_test", language), result.get("test_feedback")),
    ]
    if not any(fb for _, fb in feedback_items):
        return []
    lines = ["", get_text("notifier.github_pr_comment.category_feedback_header", language)]
    for label, fb in feedback_items:
        if fb:
            lines.append(f"- **{label}**: {fb}")
    return lines


def _file_feedback_lines(result: dict, language: str = "en") -> list[str]:
    """파일별 피드백 섹션."""
    if not result.get("file_feedbacks"):
        return []
    lines = ["", get_text("notifier.github_pr_comment.file_feedback_header", language)]
    for ff in result["file_feedbacks"]:
        lines.append(f"#### `{ff.get('file', '?')}`")
        for issue in ff.get("issues", []):
            lines.append(f"- {issue}")
    return lines


def _ai_suggestions_lines(result: dict, language: str = "en") -> list[str]:
    """AI 개선 제안 섹션."""
    if not result.get("ai_suggestions"):
        return []
    return [
        "",
        get_text("notifier.github_pr_comment.ai_suggestions_header", language),
    ] + [f"- {s}" for s in result["ai_suggestions"]]


def _static_issues_lines(result: dict, language: str = "en") -> list[str]:
    """정적 분석 이슈 섹션 (상위 N건)."""
    if not result.get("issues"):
        return []
    lines = [
        "",
        get_text(
            "notifier.github_pr_comment.issues_header", language,
            count=NOTIFIER_MAX_ISSUES_LONG,
        ),
    ]
    for issue in result["issues"][:NOTIFIER_MAX_ISSUES_LONG]:
        lines.append(
            f"- **[{issue.get('tool', '?')}]** {issue.get('message', '')} "
            f"(line {issue.get('line', '?')})"
        )
    return lines


def _incomplete_warning_lines(result: dict, language: str = "en") -> list[str]:
    """정적분석 불완전(타임아웃/전량실패) 시 점수 신뢰 불가 경고 배너 (사이클 164 follow-up #5).
    Warning banner when static analysis is incomplete — the score may be inflated/unreliable.

    `static_analysis_incomplete` 마커는 auto-merge/auto-approve 만 차단(#779/#783)할 뿐
    PR 코멘트 점수에는 무경고 노출돼 사람 수동 머지 시 오판 위험 → 점수 위에 배너 삽입.
    The marker only blocks auto-merge/approve; surface it in the PR comment so manual
    reviewers do not trust an inflated score.
    """
    if not result.get("static_analysis_incomplete"):
        return []
    return [get_text("notifier.github_pr_comment.static_incomplete_warning", language), ""]


def _build_comment_from_result(result: dict, language: str = "en") -> str:
    """Build a formatted PR comment body from a stored analysis result dict (Phase 3 PR-11 — i18n)."""
    return "\n".join(
        _incomplete_warning_lines(result, language)
        + _header_lines(result, language)
        + _ai_summary_lines(result, language)
        + _category_feedback_lines(result, language)
        + _file_feedback_lines(result, language)
        + _ai_suggestions_lines(result, language)
        + _static_issues_lines(result, language)
    )


async def post_pr_comment_from_result(
    github_token: str,
    repo_name: str,
    pr_number: int,
    result: dict,
    language: str = "en",
) -> None:
    """Post a formatted analysis result comment from a stored result dict (Phase 3 PR-11 — i18n)."""
    body = _build_comment_from_result(result, language=language)
    url = f"{GITHUB_API}/repos/{repo_name}/issues/{pr_number}/comments"
    client = get_http_client()
    r = await client.post(
        url,
        json={"body": body},
        headers=github_api_headers(github_token),
    )
    r.raise_for_status()
