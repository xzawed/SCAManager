"""GitHub pull request comment notifier using the GitHub Issues API.

Phase 3 PR-11 (사이클 84) — i18n: language 인자 + 3-layer fallback (resolve_notification_language).
Phase 3 PR-11 (Cycle 84) — i18n: language arg + 3-layer fallback.
"""
from src.constants import GITHUB_API, GRADE_EMOJI, NOTIFIER_MAX_ISSUES_LONG
from src.gate._common import ai_review_failed
from src.github_client.helpers import github_api_headers
from src.i18n.loader import get_text
from src.notifier._common import escape_markdown, resolve_ai_summary
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
    """AI 요약 섹션.

    🔴 AI 리뷰 실패(api_error/parse_error) 시 raw ai_summary(실패 fallback 문자열) 대신
    현지화된 '불가' 메시지를 노출한다 — 다른 4채널(resolve_ai_summary 경유)과 parity.
    🔴 On AI failure show the localized "unavailable" message instead of the raw fallback,
    matching the other four channels (which route through resolve_ai_summary).
    """
    if ai_review_failed(result):
        return [
            "",
            get_text("notifier.github_pr_comment.ai_summary_header", language),
            get_text("notifier.common.ai_unavailable", language),
        ]
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
        # 감사 D: untrusted 정적 도구 메시지 → markdown 이스케이프 (링크/이미지/HTML 인젝션 차단)
        # Audit D: escape untrusted static-tool message for markdown (block link/image/HTML injection)
        lines.append(
            f"- **[{issue.get('tool', '?')}]** {escape_markdown(str(issue.get('message', '')))} "
            f"(line {issue.get('line', '?')})"
        )
    return lines


def _unreliable_score_warning_lines(result: dict, language: str = "en") -> list[str]:
    """점수 신뢰 불가 경고 배너 — 정적분석 미완료 + AI 리뷰 실패 (premium audit #7, 5채널 대칭).
    Warning banner when the rendered score is inflated/unreliable — static-incomplete or AI-failed.

    두 마커 모두 auto-merge/auto-approve 만 차단(#779/#783/#804)할 뿐 PR 코멘트 점수에는
    무경고 노출된다 → 사람이 수동 머지 시 인플레 점수를 신뢰하는 오판 위험. 점수 위에 배너 삽입.
    🔴 AI 실패는 `ai_review_failed`(gate/_common 단일출처, api_error/parse_error) 로 판정 —
    의도적 skip(no_api_key/empty_diff/disabled)은 점수 유지·비차단이므로 경고 대상 아님.
    Both markers block only auto-merge/approve; surface them so a manual reviewer does not trust
    an inflated score. AI failure uses ai_review_failed (single source, mirrors the gate guard).
    """
    lines: list[str] = []
    if result.get("static_analysis_incomplete"):
        lines.append(get_text("notifier.github_pr_comment.static_incomplete_warning", language))
    if ai_review_failed(result):
        lines.append(get_text("notifier.github_pr_comment.ai_failed_warning", language))
    if lines:
        lines.append("")  # 배너와 헤더 사이 빈 줄 / blank line between banner and header
    return lines


def _build_comment_from_result(result: dict, language: str = "en") -> str:
    """Build a formatted PR comment body from a stored analysis result dict (Phase 3 PR-11 — i18n)."""
    return "\n".join(
        _unreliable_score_warning_lines(result, language)
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


async def post_plain_pr_comment(
    github_token: str, repo_name: str, pr_number: int, body: str,
) -> None:
    """임의 텍스트를 PR 에 코멘트로 게시 (검증자 차단 사유 등 — 분석 포맷과 무관한 plain 메시지).
    Post an arbitrary text comment to a PR (e.g. verifier block reason — not the analysis format).
    """
    url = f"{GITHUB_API}/repos/{repo_name}/issues/{pr_number}/comments"
    client = get_http_client()
    r = await client.post(url, json={"body": body}, headers=github_api_headers(github_token))
    r.raise_for_status()
