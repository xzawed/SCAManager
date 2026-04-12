"""Score calculator — converts static analysis and AI review results into a 0–100 score."""
from __future__ import annotations
from dataclasses import dataclass
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult


@dataclass
class ScoreResult:
    total: int
    grade: str
    code_quality_score: int
    security_score: int
    breakdown: dict


def calculate_score(
    analysis_results: list[StaticAnalysisResult],
    ai_review: AiReviewResult | None = None,
) -> ScoreResult:
    all_issues = [issue for r in analysis_results for issue in r.issues]

    pylint_errors = sum(1 for i in all_issues if i.tool == "pylint" and i.severity == "error")
    pylint_warnings = sum(1 for i in all_issues if i.tool == "pylint" and i.severity == "warning")
    flake8_warnings = sum(1 for i in all_issues if i.tool == "flake8")
    bandit_errors = sum(1 for i in all_issues if i.tool == "bandit" and i.severity == "error")
    bandit_warnings = sum(1 for i in all_issues if i.tool == "bandit" and i.severity == "warning")

    code_quality_score = max(0, 25
                             - pylint_errors * 3
                             - min(pylint_warnings, 15) * 1
                             - min(flake8_warnings, 10) * 1)
    security_score = max(0, 20 - bandit_errors * 7 - bandit_warnings * 2)

    ai_defaults_applied = False
    if ai_review is not None and ai_review.status == "success":
        # AI 점수를 새 배점으로 스케일링 (commit 0-20→0-15, ai 0-20→0-25, test 0-10→0-15)
        commit_score = round(ai_review.commit_score * 15 / 20)
        ai_score = round(ai_review.ai_score * 25 / 20)
        test_score = round(ai_review.test_score * 15 / 10)
    else:
        # AI 리뷰 없거나 기본값 적용 시 중립적 기본값 (raw 17/20, 17/20, 7/10 스케일링 상당)
        commit_score = 13
        ai_score = 21
        test_score = 10
        ai_defaults_applied = True

    total = code_quality_score + security_score + commit_score + ai_score + test_score

    breakdown: dict = {
        "code_quality": code_quality_score,
        "security": security_score,
        "commit_message": commit_score,
        "ai_review": ai_score,
        "test_coverage": test_score,
    }
    if ai_defaults_applied:
        breakdown["ai_defaults_applied"] = True

    return ScoreResult(
        total=total,
        grade=_grade(total),
        code_quality_score=code_quality_score,
        security_score=security_score,
        breakdown=breakdown,
    )


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"
