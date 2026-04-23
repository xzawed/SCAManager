"""Tests for src.cli.formatter — terminal output formatting."""
import json

from src.analyzer.io.static import StaticAnalysisResult, AnalysisIssue
from src.analyzer.io.ai_review import AiReviewResult
from src.scorer.calculator import ScoreResult
from src.cli.formatter import format_result, format_json


def _score(total=85, grade="B"):
    return ScoreResult(
        total=total,
        grade=grade,
        code_quality_score=22,
        security_score=20,
        breakdown={
            "code_quality": 22,
            "security": 20,
            "commit_message": 14,
            "ai_review": 21,
            "test_coverage": 10,
        },
    )


def _ai_review():
    return AiReviewResult(
        commit_score=17,
        ai_score=17,
        test_score=7,
        summary="Good refactoring of the module.",
        suggestions=["Add type hints", "Split large function"],
        commit_message_feedback="Clear and concise.",
        code_quality_feedback="Well structured.",
        security_feedback="No issues found.",
        direction_feedback="Good approach.",
        test_feedback="Consider edge cases.",
        file_feedbacks=[
            {"file": "src/app.py", "issues": ["Line 10: rename variable"]}
        ],
    )


def _static_results():
    return [
        StaticAnalysisResult(
            filename="src/app.py",
            issues=[
                AnalysisIssue(tool="pylint", severity="error", message="undefined-variable", line=12),
                AnalysisIssue(tool="flake8", severity="warning", message="E302 expected 2 blank lines", line=25),
            ],
        )
    ]


# ── format_result ────────────────────────────────────────

def test_format_result_contains_total_score():
    output = format_result(_score(), [], None, use_color=False)
    assert "85" in output
    assert "100" in output


def test_format_result_contains_grade():
    output = format_result(_score(), [], None, use_color=False)
    assert "B" in output


def test_format_result_contains_breakdown():
    output = format_result(_score(), [], None, use_color=False)
    assert "22" in output  # code_quality
    assert "25" in output  # max code_quality
    assert "20" in output  # security


def test_format_result_with_ai_shows_summary():
    output = format_result(_score(), [], _ai_review(), use_color=False)
    assert "Good refactoring" in output


def test_format_result_without_ai_no_summary():
    output = format_result(_score(), [], None, use_color=False)
    assert "Good refactoring" not in output


def test_format_result_shows_static_issues():
    output = format_result(_score(), _static_results(), None, use_color=False)
    assert "undefined-variable" in output
    assert "pylint" in output


def test_format_result_no_color():
    output = format_result(_score(), [], None, use_color=False)
    assert "\033[" not in output


def test_format_result_with_color():
    output = format_result(_score(), [], None, use_color=True)
    assert "\033[" in output


# ── format_json ──────────────────────────────────────────

def test_format_json_valid():
    raw = format_json(_score(), _static_results(), _ai_review())
    data = json.loads(raw)
    assert data["total"] == 85
    assert data["grade"] == "B"
    assert "breakdown" in data
    assert "ai_summary" in data
    assert len(data["issues"]) == 2
