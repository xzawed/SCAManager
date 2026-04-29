"""Phase 4 PR-T1 — scorer/calculator.py 경계값·엣지 케이스 단위 테스트.

기존 test_calculator.py 는 happy/typical 케이스 중심 — 14-에이전트 감사 R1-B 가
지적한 "등급 경계 (44/45/59/60/74/75/89/90), CQ_WARNING_CAP 경계, 모든 status
fallback 경로" 갭을 메운다.

검증 대상:
  - calculate_grade: F/D/C/B/A 모든 경계값 (44↔45, 59↔60, 74↔75, 89↔90)
  - calculate_grade: 음수·101 등 범위 초과 입력
  - calculate_score: CQ_WARNING_CAP=25 정확 경계 (24/25/26 warning)
  - calculate_score: AI status 모든 값 (no_api_key/empty_diff/api_error/parse_error)
    이 모두 ai_defaults_applied=True 로 폴백되는지
  - calculate_score: round() banker's rounding 경계 (commit_score=10 → 7.5 → 8)
  - calculate_score: 빈 analysis_results 리스트
  - calculate_score: mixed category(code_quality + security) 동시 감점
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

# pylint: disable=wrong-import-position
import pytest

from src.analyzer.io.ai_review import AiReviewResult
from src.analyzer.io.static import AnalysisIssue, StaticAnalysisResult
from src.scorer.calculator import calculate_grade, calculate_score


def _make_result(issues: list[AnalysisIssue]) -> StaticAnalysisResult:
    r = StaticAnalysisResult(filename="t.py")
    r.issues = issues
    return r


def _make_ai(commit_score=18, ai_score=17, test_score=10, status="success"):
    ai = AiReviewResult(
        commit_score=commit_score,
        ai_score=ai_score,
        test_score=test_score,
        summary="ok",
    )
    ai.status = status  # type: ignore[attr-defined]
    return ai


# ──────────────────────────────────────────────────────────────────────────
# calculate_grade — 모든 경계값
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("score,expected", [
    (100, "A"),
    (90, "A"),       # A 하한 경계
    (89, "B"),       # B 상한 경계
    (75, "B"),       # B 하한 경계
    (74, "C"),       # C 상한 경계
    (60, "C"),       # C 하한 경계
    (59, "D"),       # D 상한 경계
    (45, "D"),       # D 하한 경계
    (44, "F"),       # F 상한 경계
    (0, "F"),
])
def test_calculate_grade_all_boundaries(score: int, expected: str) -> None:
    """등급 경계값(44/45, 59/60, 74/75, 89/90) 정확성 검증."""
    assert calculate_grade(score) == expected


def test_calculate_grade_negative_returns_f():
    """음수 점수도 F (방어적)."""
    assert calculate_grade(-10) == "F"
    assert calculate_grade(-1) == "F"


def test_calculate_grade_above_100_returns_a():
    """100 초과 (clamp 전 호출 시) 도 A."""
    assert calculate_grade(101) == "A"
    assert calculate_grade(150) == "A"


# ──────────────────────────────────────────────────────────────────────────
# CQ_WARNING_CAP 경계 (= 25)
# ──────────────────────────────────────────────────────────────────────────


def test_cq_warning_cap_exactly_at_boundary():
    """warning 25개 정확 = cap 도달. cq=25-25=0."""
    issues = [AnalysisIssue(tool="pylint", severity="warning", message="w", line=i) for i in range(25)]
    result = calculate_score([_make_result(issues)])
    assert result.code_quality_score == 0


def test_cq_warning_cap_one_below_boundary():
    """warning 24개 = cap 미달. cq=25-24=1."""
    issues = [AnalysisIssue(tool="pylint", severity="warning", message="w", line=i) for i in range(24)]
    result = calculate_score([_make_result(issues)])
    assert result.code_quality_score == 1


def test_cq_warning_cap_above_boundary_no_extra_deduction():
    """warning 100개여도 cap=25 적용 → cq=0 동일."""
    issues = [AnalysisIssue(tool="pylint", severity="warning", message="w", line=i) for i in range(100)]
    result = calculate_score([_make_result(issues)])
    assert result.code_quality_score == 0


def test_cq_errors_not_capped_by_warning_cap():
    """error 는 cap 적용 안됨 — error 1개 + warning 25개 = 25 - 3 - 25 = clamp 0."""
    issues = (
        [AnalysisIssue(tool="pylint", severity="error", message="e", line=i) for i in range(1)]
        + [AnalysisIssue(tool="pylint", severity="warning", message="w", line=i) for i in range(25)]
    )
    result = calculate_score([_make_result(issues)])
    assert result.code_quality_score == 0


# ──────────────────────────────────────────────────────────────────────────
# AI status fallback — 모든 비-success status 값
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("status", ["no_api_key", "empty_diff", "api_error", "parse_error"])
def test_all_failure_statuses_apply_defaults(status: str) -> None:
    """status ∈ {no_api_key, empty_diff, api_error, parse_error} 시 ai_defaults_applied=True."""
    ai = _make_ai(status=status)
    result = calculate_score([_make_result([])], ai_review=ai)
    assert result.breakdown["ai_defaults_applied"] is True
    # 기본값: commit=13, ai=21, test=10
    assert result.breakdown["commit_message"] == 13
    assert result.breakdown["ai_review"] == 21
    assert result.breakdown["test_coverage"] == 10


def test_unknown_status_treated_as_failure():
    """status 가 알 수 없는 값이면 기본값 적용 (방어적)."""
    ai = _make_ai(status="some_future_status")
    result = calculate_score([_make_result([])], ai_review=ai)
    assert result.breakdown.get("ai_defaults_applied") is True


# ──────────────────────────────────────────────────────────────────────────
# round() banker's rounding 경계
# ──────────────────────────────────────────────────────────────────────────


def test_commit_score_10_scales_to_8_via_round():
    """commit_score=10 → 10*15/20=7.5 → round() banker → 8."""
    ai = _make_ai(commit_score=10, ai_score=10, test_score=5)
    result = calculate_score([_make_result([])], ai_review=ai)
    # round(7.5) = 8 (Python banker's rounding rounds half-to-even, 8 is even)
    assert result.breakdown["commit_message"] == 8


def test_ai_score_10_scales_via_round():
    """ai_score=10 → 10*25/20=12.5 → round() banker → 12 (12 is even)."""
    ai = _make_ai(commit_score=10, ai_score=10, test_score=5)
    result = calculate_score([_make_result([])], ai_review=ai)
    assert result.breakdown["ai_review"] == 12


def test_test_score_5_scales_via_round():
    """test_score=5 → 5*15/10=7.5 → round() banker → 8 (8 is even)."""
    ai = _make_ai(commit_score=10, ai_score=10, test_score=5)
    result = calculate_score([_make_result([])], ai_review=ai)
    assert result.breakdown["test_coverage"] == 8


# ──────────────────────────────────────────────────────────────────────────
# 빈/혼합 입력
# ──────────────────────────────────────────────────────────────────────────


def test_empty_analysis_results_list():
    """analysis_results=[] (정적 분석 미수행) — 만점 25 + 20 = 45 + AI 기본값."""
    result = calculate_score([], ai_review=None)
    assert result.code_quality_score == 25
    assert result.security_score == 20
    # 25 + 20 + 13 + 21 + 10 = 89
    assert result.total == 89
    assert result.grade == "B"


def test_multiple_analysis_results_concat_issues():
    """여러 StaticAnalysisResult 의 issues 가 합산되어 감점."""
    r1 = _make_result([AnalysisIssue(tool="pylint", severity="error", message="e", line=1)])
    r2 = _make_result([AnalysisIssue(tool="pylint", severity="error", message="e", line=2)])
    result = calculate_score([r1, r2])
    # 2 errors × 3 = 6 감점 → cq=19
    assert result.code_quality_score == 19


def test_mixed_category_independent_deduction():
    """code_quality 와 security 가 독립적으로 감점됨."""
    issues = [
        AnalysisIssue(tool="pylint", severity="error", message="e", line=1, category="code_quality"),
        AnalysisIssue(tool="bandit", severity="error", message="s", line=1, category="security"),
    ]
    result = calculate_score([_make_result(issues)])
    assert result.code_quality_score == 22  # 25 - 3
    assert result.security_score == 13       # 20 - 7


def test_security_warnings_have_separate_cap_behavior():
    """security warning 은 별도 카테고리 — cq cap 미적용."""
    issues = [
        AnalysisIssue(tool="bandit", severity="warning", message="w", line=i, category="security")
        for i in range(20)
    ]
    result = calculate_score([_make_result(issues)])
    # security = max(0, 20 - 20*2) = 0 (cap 없이 0 으로 clamp)
    assert result.security_score == 0
    assert result.code_quality_score == 25  # 영향 없음


# ──────────────────────────────────────────────────────────────────────────
# total clamp + breakdown 일관성
# ──────────────────────────────────────────────────────────────────────────


def test_breakdown_sum_matches_total_when_under_100():
    """code_quality + security + commit + ai + test 합계가 total 과 일치 (clamp 미발동)."""
    ai = _make_ai(commit_score=15, ai_score=15, test_score=8)
    result = calculate_score([_make_result([])], ai_review=ai)
    expected_sum = (
        result.breakdown["code_quality"]
        + result.breakdown["security"]
        + result.breakdown["commit_message"]
        + result.breakdown["ai_review"]
        + result.breakdown["test_coverage"]
    )
    assert result.total == expected_sum


def test_score_result_dataclass_fields():
    """ScoreResult 의 모든 필드가 올바른 타입."""
    result = calculate_score([_make_result([])], ai_review=None)
    assert isinstance(result.total, int)
    assert isinstance(result.grade, str)
    assert isinstance(result.code_quality_score, int)
    assert isinstance(result.security_score, int)
    assert isinstance(result.breakdown, dict)


def test_score_result_total_in_range():
    """total 은 항상 0-100 범위."""
    # 극단적 입력 다수 케이스
    for ai_status in ["success", "api_error"]:
        for issue_count in [0, 5, 50]:
            issues = [
                AnalysisIssue(tool="pylint", severity="error", message="e", line=i)
                for i in range(issue_count)
            ]
            ai = _make_ai(status=ai_status)
            result = calculate_score([_make_result(issues)], ai_review=ai)
            assert 0 <= result.total <= 100, f"total={result.total} out of range"
