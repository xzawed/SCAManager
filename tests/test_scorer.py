from src.scorer.calculator import calculate_score
from src.analyzer.io.static import StaticAnalysisResult, AnalysisIssue


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
    issues = [AnalysisIssue(tool="bandit", severity="error", message="use of eval", line=1, category="security")]
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
        AnalysisIssue(tool="bandit", severity="error", message="sec", line=i, category="security")
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


from src.analyzer.io.ai_review import AiReviewResult


def _make_ai_review(commit_score=18, ai_score=17, test_score=10):
    return AiReviewResult(
        commit_score=commit_score,
        ai_score=ai_score,
        test_score=test_score,
        summary="ok",
        suggestions=[],
    )


def test_calculate_score_uses_ai_review_scores():
    """AI 점수가 새 배점으로 스케일링되는지 확인."""
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(commit_score=18, ai_score=17))
    # commit: round(18*15/20) = round(13.5) = 14, ai: round(17*25/20) = round(21.25) = 21
    assert result.breakdown["commit_message"] == 14
    assert result.breakdown["ai_review"] == 21


def test_calculate_score_test_coverage_max_when_full_score():
    """test_score=10 → 스케일링 후 15점."""
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(test_score=10))
    assert result.breakdown["test_coverage"] == 15


def test_calculate_score_test_coverage_0_when_no_tests():
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(test_score=0))
    assert result.breakdown["test_coverage"] == 0


def test_calculate_score_test_coverage_graduated():
    """test_score=7 → round(7*15/10) = round(10.5) = 10."""
    result = calculate_score([_make_result([])], ai_review=_make_ai_review(test_score=7))
    assert result.breakdown["test_coverage"] == 10


def test_calculate_score_fallback_when_no_ai_review():
    """AI 리뷰 없을 때 중립적 기본값 (스케일링 후)."""
    result = calculate_score([_make_result([])], ai_review=None)
    assert result.breakdown["commit_message"] == 13
    assert result.breakdown["ai_review"] == 21
    assert result.breakdown["test_coverage"] == 10
    # 25 + 20 + 13 + 21 + 10 = 89
    assert result.total == 89
    assert result.grade == "B"


def test_calculate_score_total_with_ai_review():
    result = calculate_score(
        [_make_result([])],
        ai_review=_make_ai_review(commit_score=20, ai_score=20, test_score=10),
    )
    # code_quality=25, security=20, commit=20, ai=25, test=10 = 100
    assert result.total == 100
    assert result.grade == "A"


def test_pylint_error_deduction_capped():
    """pylint error 감점이 error당 -3으로 완화되었는지 확인."""
    issues = [AnalysisIssue(tool="pylint", severity="error", message="err", line=i) for i in range(4)]
    result = calculate_score([_make_result(issues)])
    # code_quality = max(0, 25 - 4*3) = 13
    assert result.code_quality_score == 13


def test_warning_cap_limits_deduction():
    """code_quality warning 감점이 CQ_WARNING_CAP(25)에서 cap되는지 확인."""
    issues = [AnalysisIssue(tool="pylint", severity="warning", message="w", line=i) for i in range(30)]
    result = calculate_score([_make_result(issues)])
    # cq_warnings=30이지만 min(30,25)=25만 감점 → 25 - 25 = 0
    assert result.code_quality_score == 0


def test_flake8_cap_limits_deduction():
    """flake8 경고도 code_quality로 분류되어 CQ_WARNING_CAP(25) 단일 cap 적용."""
    issues = [AnalysisIssue(tool="flake8", severity="warning", message="f", line=i) for i in range(20)]
    result = calculate_score([_make_result(issues)])
    # cq_warnings=20이지만 min(20,25)=20만 감점 → 25 - 20 = 5
    assert result.code_quality_score == 5


def test_bandit_error_deduction_reduced():
    """security error(bandit HIGH) 감점이 -7로 완화되었는지 확인."""
    issues = [AnalysisIssue(tool="bandit", severity="error", message="eval", line=1, category="security")]
    result = calculate_score([_make_result(issues)])
    # security = max(0, 20 - 1*7) = 13
    assert result.security_score == 13


def test_bandit_warning_deduction_reduced():
    """security warning(bandit LOW) 감점이 -2로 완화되었는지 확인."""
    issues = [AnalysisIssue(tool="bandit", severity="warning", message="w", line=i, category="security") for i in range(3)]
    result = calculate_score([_make_result(issues)])
    # security = max(0, 20 - 3*2) = 14
    assert result.security_score == 14


def test_new_weight_distribution():
    """배점 비중 재조정 확인: code_quality=25, commit=15, ai=25, test=15."""
    result = calculate_score(
        [_make_result([])],
        ai_review=_make_ai_review(commit_score=20, ai_score=20, test_score=10),
    )
    # code_quality max=25, security max=20, commit 20→15 scaled, ai 20→25 scaled, test 10→15 scaled
    assert result.breakdown["code_quality"] == 25
    assert result.breakdown["commit_message"] == 15
    assert result.breakdown["ai_review"] == 25
    assert result.breakdown["test_coverage"] == 15
    assert result.total == 100


# ---------------------------------------------------------------------------
# Task 1 — breakdown["ai_defaults_applied"] 플래그 테스트
# (Red 단계: calculate_score가 아직 ai_defaults_applied 플래그를 반환하지 않음)
# ---------------------------------------------------------------------------

def test_breakdown_has_ai_defaults_flag_when_no_review():
    # ai_review=None 이면 breakdown에 ai_defaults_applied == True 가 포함되어야 한다
    result = calculate_score([_make_result([])], ai_review=None)
    assert result.breakdown.get("ai_defaults_applied") is True


def test_breakdown_has_ai_defaults_flag_when_default_status():
    # ai_review.status == "no_api_key" 이면 ai_defaults_applied == True 이어야 한다
    ai = _make_ai_review()
    ai.status = "no_api_key"  # type: ignore[attr-defined]
    result = calculate_score([_make_result([])], ai_review=ai)
    assert result.breakdown.get("ai_defaults_applied") is True


def test_breakdown_has_ai_defaults_flag_when_api_error_status():
    # ai_review.status == "api_error" 이면 ai_defaults_applied == True 이어야 한다
    ai = _make_ai_review()
    ai.status = "api_error"  # type: ignore[attr-defined]
    result = calculate_score([_make_result([])], ai_review=ai)
    assert result.breakdown.get("ai_defaults_applied") is True


def test_breakdown_no_ai_defaults_flag_on_success():
    # ai_review.status == "success" 이면 ai_defaults_applied 키가 breakdown에 없어야 한다
    ai = _make_ai_review()
    ai.status = "success"  # type: ignore[attr-defined]
    result = calculate_score([_make_result([])], ai_review=ai)
    assert "ai_defaults_applied" not in result.breakdown


# ---------------------------------------------------------------------------
# P2-14 — total 점수 0-100 clamp
# ---------------------------------------------------------------------------

def test_total_score_clamped_to_100():
    """비정상적으로 높은 AI 점수 입력 시 총점이 100을 초과하지 않아야 한다."""
    # raw 점수가 상한을 넘어도 total은 100으로 고정
    ai = AiReviewResult(
        commit_score=20, ai_score=20, test_score=10,
        summary="ok", suggestions=[],
    )
    ai.status = "success"  # type: ignore[attr-defined]
    result = calculate_score([_make_result([])], ai_review=ai)
    assert result.total <= 100


def test_total_score_cannot_be_negative():
    """과도한 감점이 있어도 총점이 음수가 되지 않아야 한다."""
    issues = (
        [AnalysisIssue(tool="pylint", severity="error", message="e", line=i) for i in range(50)]
        + [AnalysisIssue(tool="bandit", severity="error", message="b", line=i) for i in range(10)]
    )
    result = calculate_score([_make_result(issues)], ai_review=None)
    assert result.total >= 0
