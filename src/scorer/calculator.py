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

    code_quality_score = max(0, 30 - pylint_errors * 5 - pylint_warnings * 1 - flake8_warnings * 1)
    security_score = max(0, 20 - bandit_errors * 10 - bandit_warnings * 3)

    if ai_review is not None:
        commit_score = ai_review.commit_score
        ai_score = ai_review.ai_score
        test_score = 10 if ai_review.has_tests else 0
    else:
        # AI 리뷰 없을 때 Phase 1 호환 기본값
        commit_score = 15
        ai_score = 15
        test_score = 5

    total = code_quality_score + security_score + commit_score + ai_score + test_score

    return ScoreResult(
        total=total,
        grade=_grade(total),
        code_quality_score=code_quality_score,
        security_score=security_score,
        breakdown={
            "code_quality": code_quality_score,
            "security": security_score,
            "commit_message": commit_score,
            "ai_review": ai_score,
            "test_coverage": test_score,
        },
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
