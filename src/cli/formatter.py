"""Terminal output formatting for CLI code review results."""
import json
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult
from src.scorer.calculator import ScoreResult

_GRADE_EMOJI = {"A": "\U0001f7e2", "B": "\U0001f535", "C": "\U0001f7e1", "D": "\U0001f7e0", "F": "\U0001f534"}
_GRADE_COLOR = {"A": 32, "B": 34, "C": 33, "D": 33, "F": 31}

_CATEGORIES = [
    ("Code Quality", "code_quality", 25),
    ("Security", "security", 20),
    ("Commit Message", "commit_message", 15),
    ("Direction (AI)", "ai_review", 25),
    ("Test Coverage", "test_coverage", 15),
]


def _c(text: str, code: int, enabled: bool) -> str:
    if not enabled:
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(text: str, enabled: bool) -> str:
    return _c(text, 1, enabled)


def format_result(
    score: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
    *,
    use_color: bool = True,
) -> str:
    lines: list[str] = []
    bd = score.breakdown
    emoji = _GRADE_EMOJI.get(score.grade, "")
    gc = _GRADE_COLOR.get(score.grade, 0)

    # header
    sep = "\u2501" * 40
    lines.append("")
    lines.append(_bold(sep, use_color))
    lines.append(_bold("  SCAManager Code Review", use_color))
    lines.append(_bold(sep, use_color))
    lines.append("")

    # score banner
    score_text = f"  Total: {_c(str(score.total), gc, use_color)}/100  Grade: {_c(score.grade, gc, use_color)} {emoji}"
    lines.append(score_text)
    lines.append("")

    # breakdown table
    lines.append(_bold("  Score Breakdown:", use_color))
    _H = "\u2500"
    lines.append(f"  \u250c{_H*18}\u252c{_H*7}\u252c{_H*6}\u2510")
    lines.append("  \u2502 Category         \u2502 Score \u2502  Max \u2502")
    lines.append(f"  \u251c{_H*18}\u253c{_H*7}\u253c{_H*6}\u2524")
    for label, key, mx in _CATEGORIES:
        val = bd.get(key, 0)
        lines.append(f"  \u2502 {label:<16} \u2502 {val:>5} \u2502 {mx:>4} \u2502")
    lines.append(f"  \u2514{_H*18}\u2534{_H*7}\u2534{_H*6}\u2518")
    lines.append("")

    # AI review sections
    if ai_review:
        if ai_review.summary:
            lines.append(_bold("  AI Summary:", use_color))
            lines.append(f"    {ai_review.summary}")
            lines.append("")

        if ai_review.suggestions:
            lines.append(_bold("  Suggestions:", use_color))
            for s in ai_review.suggestions:
                lines.append(f"    - {s}")
            lines.append("")

        # category feedback
        fb_items = [
            ("Commit Message", ai_review.commit_message_feedback),
            ("Code Quality", ai_review.code_quality_feedback),
            ("Security", ai_review.security_feedback),
            ("Direction", ai_review.direction_feedback),
            ("Test", ai_review.test_feedback),
        ]
        has_fb = any(fb for _, fb in fb_items)
        if has_fb:
            lines.append(_bold("  Category Feedback:", use_color))
            for label, fb in fb_items:
                if fb:
                    lines.append(f"    [{label}] {fb}")
            lines.append("")

        # file feedback
        if ai_review.file_feedbacks:
            lines.append(_bold("  File Feedback:", use_color))
            for ff in ai_review.file_feedbacks:
                lines.append(f"    {ff.get('file', '?')}:")
                for issue in ff.get("issues", []):
                    lines.append(f"      - {issue}")
            lines.append("")

    # static analysis issues
    all_issues = [(r.filename, i) for r in analysis_results for i in r.issues]
    if all_issues:
        lines.append(_bold(f"  Static Analysis Issues ({len(all_issues)}건):", use_color))
        for fname, iss in all_issues:
            sev_color = 31 if iss.severity == "error" else 33
            tag = _c(f"[{iss.tool}/{iss.severity}]", sev_color, use_color)
            loc = f"{fname}:{iss.line}" if iss.line else fname
            lines.append(f"    {loc} {tag} {iss.message}")
        lines.append("")

    lines.append(_bold(sep, use_color))
    lines.append("")
    return "\n".join(lines)


def format_json(
    score: ScoreResult,
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None,
) -> str:
    issues = []
    for r in analysis_results:
        for i in r.issues:
            issues.append({
                "file": r.filename,
                "tool": i.tool,
                "severity": i.severity,
                "message": i.message,
                "line": i.line,
            })

    data = {
        "total": score.total,
        "grade": score.grade,
        "breakdown": score.breakdown,
        "issues": issues,
        "ai_summary": ai_review.summary if ai_review else None,
        "ai_suggestions": ai_review.suggestions if ai_review else [],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
