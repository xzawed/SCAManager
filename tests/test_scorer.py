from src.scorer.calculator import calculate_score, ScoreResult
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
