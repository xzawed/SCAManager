"""Score calculator — converts static analysis and AI review results into a 0–100 score."""
from __future__ import annotations
from dataclasses import dataclass
from src.analyzer.static import StaticAnalysisResult
from src.analyzer.ai_review import AiReviewResult
from src.constants import (
    CODE_QUALITY_MAX, SECURITY_MAX,
    COMMIT_MSG_MAX, AI_REVIEW_MAX, TEST_COVERAGE_MAX,
    PYLINT_ERROR_PENALTY, PYLINT_WARNING_PENALTY, CQ_WARNING_CAP,
    BANDIT_HIGH_PENALTY, BANDIT_LOW_PENALTY,
    AI_DEFAULT_COMMIT, AI_DEFAULT_DIRECTION, AI_DEFAULT_TEST,
    GRADE_THRESHOLDS,
)


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
    """정적분석 결과와 AI 리뷰로부터 0–100 점수와 등급을 계산한다.

    Args:
        analysis_results: pylint·flake8·bandit 결과 목록 (빈 목록 허용)
        ai_review:        Claude AI 리뷰 결과 (None이거나 status != "success"면 기본값 적용)

    Returns:
        ScoreResult(total, grade, code_quality_score, security_score, breakdown)

    점수 체계 (합계 100점):
        코드품질(25) + 보안(20) + 커밋메시지(15) + AI방향성(25) + 테스트(15)
    """
    all_issues = [issue for r in analysis_results for issue in r.issues]

    # category 기반 집계 — tool 이름에 무관하게 미래 도구(Semgrep 등)도 동일하게 처리
    cq_errors   = sum(1 for i in all_issues if i.category == "code_quality" and i.severity == "error")
    cq_warnings = sum(1 for i in all_issues if i.category == "code_quality" and i.severity == "warning")
    sec_errors  = sum(1 for i in all_issues if i.category == "security" and i.severity == "error")
    sec_warnings = sum(1 for i in all_issues if i.category == "security" and i.severity == "warning")

    code_quality_score = max(0, CODE_QUALITY_MAX
                             - cq_errors * PYLINT_ERROR_PENALTY
                             - min(cq_warnings, CQ_WARNING_CAP) * PYLINT_WARNING_PENALTY)
    security_score = max(0, SECURITY_MAX
                         - sec_errors * BANDIT_HIGH_PENALTY
                         - sec_warnings * BANDIT_LOW_PENALTY)

    ai_defaults_applied = False
    if ai_review is not None and ai_review.status == "success":
        # AI 점수를 새 배점으로 스케일링 (commit 0-20→0-15, ai 0-20→0-25, test 0-10→0-15)
        commit_score = round(ai_review.commit_score * COMMIT_MSG_MAX / 20)
        ai_score = round(ai_review.ai_score * AI_REVIEW_MAX / 20)
        test_score = round(ai_review.test_score * TEST_COVERAGE_MAX / 10)
    else:
        # AI 리뷰 없거나 기본값 적용 시 중립적 기본값
        commit_score = AI_DEFAULT_COMMIT
        ai_score = AI_DEFAULT_DIRECTION
        test_score = AI_DEFAULT_TEST
        ai_defaults_applied = True

    total = max(0, min(code_quality_score + security_score + commit_score + ai_score + test_score, 100))

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
    for grade, threshold in GRADE_THRESHOLDS.items():
        if score >= threshold:
            return grade
    return "F"
