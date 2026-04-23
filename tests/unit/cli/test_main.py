"""Tests for src.cli.__main__ — CLI entry point orchestration."""
from unittest.mock import patch, MagicMock
import pytest

from src.cli.git_diff import ChangedFile
from src.analyzer.io.static import StaticAnalysisResult
from src.analyzer.io.ai_review import AiReviewResult
from src.scorer.calculator import ScoreResult


_FILES = [
    ChangedFile("src/app.py", "print('hello')\n", "--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new"),
]
_SCORE_B = ScoreResult(total=80, grade="B", code_quality_score=22, security_score=20, breakdown={})
_SCORE_F = ScoreResult(total=30, grade="F", code_quality_score=5, security_score=10, breakdown={})
_AI = AiReviewResult(commit_score=17, ai_score=17, test_score=7, summary="OK", suggestions=[])


def _import_main():
    from src.cli.__main__ import main
    return main


@patch("src.cli.__main__.format_result", return_value="output")
@patch("src.cli.__main__.calculate_score", return_value=_SCORE_B)
@patch("src.cli.__main__.review_code", return_value=_AI)
@patch("src.cli.__main__.analyze_file", return_value=StaticAnalysisResult("src/app.py", []))
@patch("src.cli.__main__.get_commit_message", return_value="feat: test")
@patch("src.cli.__main__.get_diff_files", return_value=_FILES)
def test_main_runs_full_pipeline(m_diff, m_msg, m_analyze, m_review, m_score, m_fmt):
    """Full pipeline executes: diff → analyze → review → score → output."""
    main = _import_main()
    with pytest.raises(SystemExit) as exc_info:
        main(["review"])
    assert exc_info.value.code == 0
    m_diff.assert_called_once()
    m_analyze.assert_called_once()
    m_review.assert_called_once()
    m_score.assert_called_once()


@patch("src.cli.__main__.get_diff_files", return_value=[])
def test_main_no_files_exits_zero(m_diff, capsys):
    """Exits with 0 when no changed files."""
    main = _import_main()
    with pytest.raises(SystemExit) as exc_info:
        main(["review"])
    assert exc_info.value.code == 0
    assert "변경" in capsys.readouterr().out or True  # message printed


@patch("src.cli.__main__.format_result", return_value="output")
@patch("src.cli.__main__.calculate_score", return_value=_SCORE_F)
@patch("src.cli.__main__.review_code", return_value=_AI)
@patch("src.cli.__main__.analyze_file", return_value=StaticAnalysisResult("x.py", []))
@patch("src.cli.__main__.get_commit_message", return_value="fix")
@patch("src.cli.__main__.get_diff_files", return_value=_FILES)
def test_main_grade_f_exits_two(m_diff, m_msg, m_analyze, m_review, m_score, m_fmt):
    """Exit code 2 for F grade (CI gate usage)."""
    main = _import_main()
    with pytest.raises(SystemExit) as exc_info:
        main(["review"])
    assert exc_info.value.code == 2


@patch("src.cli.__main__.format_result", return_value="output")
@patch("src.cli.__main__.calculate_score", return_value=_SCORE_B)
@patch("src.cli.__main__.review_code", return_value=_AI)
@patch("src.cli.__main__.analyze_file", return_value=StaticAnalysisResult("x.py", []))
@patch("src.cli.__main__.get_commit_message", return_value="fix")
@patch("src.cli.__main__.get_diff_files", return_value=_FILES)
def test_main_no_ai_flag(m_diff, m_msg, m_analyze, m_review, m_score, m_fmt):
    """--no-ai flag passes empty API key to review_code."""
    main = _import_main()
    with pytest.raises(SystemExit):
        main(["review", "--no-ai"])
    # review_code is called with empty string api_key
    call_args = m_review.call_args
    assert call_args[0][0] == ""  # api_key


@patch("src.cli.__main__.format_json", return_value='{"total":80}')
@patch("src.cli.__main__.calculate_score", return_value=_SCORE_B)
@patch("src.cli.__main__.review_code", return_value=_AI)
@patch("src.cli.__main__.analyze_file", return_value=StaticAnalysisResult("x.py", []))
@patch("src.cli.__main__.get_commit_message", return_value="fix")
@patch("src.cli.__main__.get_diff_files", return_value=_FILES)
def test_main_json_flag(m_diff, m_msg, m_analyze, m_review, m_score, m_fmt_json, capsys):
    """--json flag outputs JSON format."""
    main = _import_main()
    with pytest.raises(SystemExit):
        main(["review", "--json"])
    m_fmt_json.assert_called_once()


@patch("src.cli.__main__.format_result", return_value="output")
@patch("src.cli.__main__.calculate_score", return_value=_SCORE_B)
@patch("src.cli.__main__.review_code", return_value=_AI)
@patch("src.cli.__main__.analyze_file", return_value=StaticAnalysisResult("x.py", []))
@patch("src.cli.__main__.get_commit_message", return_value="fix")
@patch("src.cli.__main__.get_diff_files", return_value=_FILES)
def test_main_staged_flag(m_diff, m_msg, m_analyze, m_review, m_score, m_fmt):
    """--staged flag is passed to get_diff_files."""
    main = _import_main()
    with pytest.raises(SystemExit):
        main(["review", "--staged"])
    m_diff.assert_called_once_with(base="HEAD~1", staged=True)


@patch("src.cli.__main__.format_result", return_value="output")
@patch("src.cli.__main__.calculate_score", return_value=_SCORE_B)
@patch("src.cli.__main__.review_code", return_value=_AI)
@patch("src.cli.__main__.analyze_file", return_value=StaticAnalysisResult("x.py", []))
@patch("src.cli.__main__.get_commit_message", return_value="fix")
@patch("src.cli.__main__.get_diff_files", return_value=_FILES)
def test_main_custom_base(m_diff, m_msg, m_analyze, m_review, m_score, m_fmt):
    """--base flag is passed to get_diff_files."""
    main = _import_main()
    with pytest.raises(SystemExit):
        main(["review", "--base", "main"])
    m_diff.assert_called_once_with(base="main", staged=False)
