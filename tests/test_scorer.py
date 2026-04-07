from src.scorer.calculator import calculate_score
from src.analyzer.static import StaticAnalysisResult, AnalysisIssue


def _make_result(issues: list[AnalysisIssue]) -> StaticAnalysisResult:
    r = StaticAnalysisResult(filename="test.py")
    r.issues = issues
    return r


def test_no_issues_gives_high_score():
    result = calculate_score([_make_result([])])
    assert result.total >= 70
    assert result.grade in ("A", "B")

def test_many_errors_lowers_score():
    issues = [AnalysisIssue(tool="pylint", severity="error", message="err", line=i) for i in range(10)]
    result = calculate_score([_make_result(issues)])
    no_issue_result = calculate_score([_make_result([])])
    assert result.total < no_issue_result.total

def test_bandit_high_severity_lowers_security_score():
    issues = [AnalysisIssue(tool="bandit", severity="error", message="use of eval", line=1)]
    result = calculate_score([_make_result(issues)])
    assert result.security_score < 20

def test_grade_a_for_score_90_plus():
    result = calculate_score([_make_result([])])
    if result.total >= 90:
        assert result.grade == "A"

def test_grade_f_for_low_score():
    many_issues = [
        AnalysisIssue(tool="pylint", severity="error", message="e", line=i)
        for i in range(20)
    ] + [
        AnalysisIssue(tool="bandit", severity="error", message="sec", line=i)
        for i in range(5)
    ]
    result = calculate_score([_make_result(many_issues)])
    assert result.grade in ("D", "F")

def test_breakdown_keys_present():
    result = calculate_score([_make_result([])])
    assert "code_quality" in result.breakdown
    assert "security" in result.breakdown
    assert "commit_message" in result.breakdown
    assert "ai_review" in result.breakdown
    assert "test_coverage" in result.breakdown


from src.analyzer.ai_review import AiReviewResult


def _make_ai_review(commit_score=18, ai_score=17, test_score=10):
    return AiReviewResult(
        commit_score=commit_score,
        ai_score=ai_score,
        test_score=test_score,
        summary="ok",
        suggestions=[],
    )


def test_calculate_score_uses_ai_review_scores():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(commit_score=18, ai_score=17))
    assert result.breakdown["commit_message"] == 18
    assert result.breakdown["ai_review"] == 17


def test_calculate_score_test_coverage_10_when_full_score():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(test_score=10))
    assert result.breakdown["test_coverage"] == 10


def test_calculate_score_test_coverage_0_when_no_tests():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(test_score=0))
    assert result.breakdown["test_coverage"] == 0


def test_calculate_score_test_coverage_graduated():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(test_score=7))
    assert result.breakdown["test_coverage"] == 7


def test_calculate_score_fallback_when_no_ai_review():
    result = calculate_score([_make_result([])], ai_review=None)
    assert result.breakdown["commit_message"] == 15
    assert result.breakdown["ai_review"] == 15
    assert result.breakdown["test_coverage"] == 5


def test_calculate_score_total_with_ai_review():
    result = calculate_score(
        [_make_result([])],
        ai_review=_make_ai_review(commit_score=20, ai_score=20, test_score=10),
    )
    # code_quality=30, security=20, commit=20, ai=20, test=10 = 100
    assert result.total == 100
    assert result.grade == "A"
