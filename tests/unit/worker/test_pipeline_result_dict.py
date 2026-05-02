"""build_analysis_result_dict 회귀 가드 — Analysis.result JSON 직렬화 보강.

Issue: Phase 11 시점 build_analysis_result_dict 가 issues JSON 에 category /
language 필드를 직렬화하지 않았음 (pipeline.py:75-79). dashboard 재설계
기획 (PR #181) 의 데이터 자산 정찰에서 발견 — 향후 언어별·카테고리별
사후 분석 차단 위험.

본 모듈은 직렬화 필드 6 종 (tool, severity, message, line, category, language)
보존을 회귀 가드로 검증.

Regression guard for build_analysis_result_dict — ensures issues JSON contains
all 6 fields so future dashboards can slice by language/category.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from src.worker.pipeline import build_analysis_result_dict


# ─── 더블 (의존성 모킹) ─────────────────────────────────────────────────────


@dataclass
class _StubIssue:
    tool: str = "pylint"
    severity: str = "warning"
    message: str = "unused import"
    line: int = 12
    category: str = "code_quality"
    language: str = "python"


@dataclass
class _StubAnalysisResult:
    issues: list[_StubIssue] = field(default_factory=list)


def _make_ai_review() -> SimpleNamespace:
    """AiReviewResult 형 더블 — pipeline 함수가 attribute 만 사용하므로 SimpleNamespace 충분."""
    return SimpleNamespace(
        status="success",
        summary="ok",
        suggestions=[],
        commit_message_feedback="commit ok",
        code_quality_feedback="cq ok",
        security_feedback="sec ok",
        direction_feedback="dir ok",
        test_feedback="test ok",
        file_feedbacks=[],
    )


def _make_score_result(total: int = 80) -> SimpleNamespace:
    return SimpleNamespace(
        total=total,
        grade="B",
        breakdown={"code_quality": 25, "security": 18, "commit_message": 13, "ai_review": 21, "test_coverage": 8},
    )


# ─── 회귀 가드 ──────────────────────────────────────────────────────────────


def test_issues_json_contains_six_fields() -> None:
    """issues JSON 의 각 항목은 6 필드 (tool/severity/message/line/category/language) 모두 포함.

    Phase 11 ~ 그룹 58 사이에는 4 필드 (tool/severity/message/line) 만 직렬화됐었다.
    PR (그룹 58 후속) 에서 category + language 추가. 본 가드가 silent 회귀 차단.
    """
    issue = _StubIssue(category="security", language="ruby")
    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[_StubAnalysisResult(issues=[issue])],
        source="pr",
    )

    assert "issues" in result, "issues 키 자체 누락"
    assert len(result["issues"]) == 1, f"issues 개수 불일치: {len(result['issues'])}"

    issue_dict: dict[str, Any] = result["issues"][0]
    expected_keys = {"tool", "severity", "message", "line", "category", "language"}
    actual_keys = set(issue_dict.keys())
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys
    assert not missing, f"필수 필드 누락 (silent 회귀): {missing}"
    assert not extra, f"예상 외 필드 추가 (스키마 검증 필요): {extra}"

    # 값 보존 검증
    assert issue_dict["tool"] == "pylint"
    assert issue_dict["severity"] == "warning"
    assert issue_dict["message"] == "unused import"
    assert issue_dict["line"] == 12
    assert issue_dict["category"] == "security"
    assert issue_dict["language"] == "ruby"


def test_issues_json_multi_results_preserves_order() -> None:
    """여러 analysis_result 의 issues 가 모두 순서대로 직렬화."""
    r1 = _StubAnalysisResult(issues=[
        _StubIssue(tool="pylint", message="A", language="python", category="code_quality"),
        _StubIssue(tool="bandit", message="B", language="python", category="security"),
    ])
    r2 = _StubAnalysisResult(issues=[
        _StubIssue(tool="rubocop", message="C", language="ruby", category="code_quality"),
    ])

    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[r1, r2],
        source="push",
    )

    assert len(result["issues"]) == 3
    assert [i["message"] for i in result["issues"]] == ["A", "B", "C"]
    assert [i["language"] for i in result["issues"]] == ["python", "python", "ruby"]
    assert [i["category"] for i in result["issues"]] == ["code_quality", "security", "code_quality"]


def test_issues_json_empty_when_no_issues() -> None:
    """이슈 0건일 때 issues 는 빈 리스트 (None 아님)."""
    result = build_analysis_result_dict(
        ai_review=_make_ai_review(),
        score_result=_make_score_result(),
        analysis_results=[_StubAnalysisResult(issues=[])],
        source="cli",
    )
    assert result["issues"] == [], "이슈 0건 시 빈 리스트여야 함 (None 또는 누락 X)"
