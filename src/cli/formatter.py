"""Terminal output formatting for CLI code review results."""
import json
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult
from src.scorer.calculator import ScoreResult
from src.constants import GRADE_EMOJI as _GRADE_EMOJI, GRADE_COLOR_ANSI as _GRADE_COLOR

_CATEGORIES = [
    ("Code Quality", "code_quality", 25),
    ("Security", "security", 20),
    ("Commit Message", "commit_message", 15),
    ("Direction (AI)", "ai_review", 25),
    ("Test Coverage", "test_coverage", 15),
]
_SEP = "\u2501" * 40
_H = "\u2500"


def _c(text: str, code: int, enabled: bool) -> str:
    """ANSI 색상 코드 적용. enabled=False이면 원문 반환."""
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(text: str, enabled: bool) -> str:
    """굵은 글씨 ANSI 코드 적용."""
    return _c(text, 1, enabled)


# ── 섹션별 헬퍼 ───────────────────────────────────────────────────────────


def _format_header(score: ScoreResult, use_color: bool) -> list[str]:
    """제목 배너 + 총점/등급 줄 생성."""
    gc = _GRADE_COLOR.get(score.grade, 0)
    emoji = _GRADE_EMOJI.get(score.grade, "")
    return [
        "",
        _bold(_SEP, use_color),
        _bold("  SCAManager Code Review", use_color),
        _bold(_SEP, use_color),
        "",
        f"  Total: {_c(str(score.total), gc, use_color)}/100  "
        f"Grade: {_c(score.grade, gc, use_color)} {emoji}",
        "",
    ]


def _format_breakdown(score: ScoreResult, use_color: bool) -> list[str]:
    """점수 분류 테이블 줄 생성."""
    bd = score.breakdown
    lines = [
        _bold("  Score Breakdown:", use_color),
        f"  \u250c{_H*18}\u252c{_H*7}\u252c{_H*6}\u2510",
        "  \u2502 Category         \u2502 Score \u2502  Max \u2502",
        f"  \u251c{_H*18}\u253c{_H*7}\u253c{_H*6}\u2524",
    ]
    for label, key, mx in _CATEGORIES:
        val = bd.get(key, 0)
        lines.append(f"  \u2502 {label:<16} \u2502 {val:>5} \u2502 {mx:>4} \u2502")
    lines.append(f"  \u2514{_H*18}\u2534{_H*7}\u2534{_H*6}\u2518")
    lines.append("")
    return lines


def _format_ai_review(ai_review: AiReviewResult, use_color: bool) -> list[str]:
    """AI 리뷰 섹션 (요약·제안·카테고리 피드백·파일 피드백) 줄 생성."""
    lines: list[str] = []

    if ai_review.summary:
        lines += [_bold("  AI Summary:", use_color), f"    {ai_review.summary}", ""]

    if ai_review.suggestions:
        lines.append(_bold("  Suggestions:", use_color))
        for s in ai_review.suggestions:
            lines.append(f"    - {s}")
        lines.append("")

    fb_items = [
        ("Commit Message", ai_review.commit_message_feedback),
        ("Code Quality", ai_review.code_quality_feedback),
        ("Security", ai_review.security_feedback),
        ("Direction", ai_review.direction_feedback),
        ("Test", ai_review.test_feedback),
    ]
    if any(fb for _, fb in fb_items):
        lines.append(_bold("  Category Feedback:", use_color))
        for label, fb in fb_items:
            if fb:
                lines.append(f"    [{label}] {fb}")
        lines.append("")

    if ai_review.file_feedbacks:
        lines.append(_bold("  File Feedback:", use_color))
        for ff in ai_review.file_feedbacks:
            lines.append(f"    {ff.get('file', '?')}:")
            for issue in ff.get("issues", []):
                lines.append(f"      - {issue}")
        lines.append("")

    return lines


def _format_static_issues(
    analysis_results: list[StaticAnalysisResult], use_color: bool
) -> list[str]:
    """정적 분석 이슈 목록 줄 생성."""
    all_issues = [(r.filename, i) for r in analysis_results for i in r.issues]
    if not all_issues:
        return []
    lines = [_bold(f"  Static Analysis Issues ({len(all_issues)}건):", use_color)]
    for fname, iss in all_issues:
        sev_color = 31 if iss.severity == "error" else 33
        tag = _c(f"[{iss.tool}/{iss.severity}]", sev_color, use_color)
        loc = f"{fname}:{iss.line}" if iss.line else fname
        lines.append(f"    {loc} {tag} {iss.message}")
    lines.append("")
    return lines


# ── 공개 API ─────────────────────────────────────────────────────────────


def format_result(
    score: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
    *,
    use_color: bool = True,
) -> str:
    """분석 결과를 터미널 출력용 문자열로 포맷한다."""
    lines: list[str] = []
    lines += _format_header(score, use_color)
    lines += _format_breakdown(score, use_color)
    if ai_review:
        lines += _format_ai_review(ai_review, use_color)
    lines += _format_static_issues(analysis_results, use_color)
    lines += [_bold(_SEP, use_color), ""]
    return "\n".join(lines)


def format_json(
    score: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
) -> str:
    """분석 결과를 JSON 문자열로 직렬화한다."""
    issues = [
        {
            "file": r.filename,
            "tool": i.tool,
            "severity": i.severity,
            "message": i.message,
            "line": i.line,
        }
        for r in analysis_results
        for i in r.issues
    ]
    data = {
        "total": score.total,
        "grade": score.grade,
        "breakdown": score.breakdown,
        "issues": issues,
        "ai_summary": ai_review.summary if ai_review else None,
        "ai_suggestions": ai_review.suggestions if ai_review else [],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
