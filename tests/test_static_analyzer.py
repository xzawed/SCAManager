from src.analyzer.static import analyze_file, StaticAnalysisResult, AnalysisIssue

CLEAN_CODE = """\
def add(a: int, b: int) -> int:
    return a + b
"""

BAD_CODE = """\
import os
x=1+2
password = "hardcoded_secret_123"
eval(input())
"""

def test_clean_code_has_no_errors():
    result = analyze_file("clean.py", CLEAN_CODE)
    assert isinstance(result, StaticAnalysisResult)
    errors = [i for i in result.issues if i.severity == "error"]
    assert len(errors) == 0

def test_bad_code_detects_issues():
    result = analyze_file("bad.py", BAD_CODE)
    assert len(result.issues) > 0

def test_bandit_detects_eval():
    result = analyze_file("eval.py", "eval(input())\n")
    bandit_issues = [i for i in result.issues if i.tool == "bandit"]
    assert len(bandit_issues) > 0

def test_result_has_correct_filename():
    result = analyze_file("myfile.py", CLEAN_CODE)
    assert result.filename == "myfile.py"

def test_empty_content_returns_no_issues():
    result = analyze_file("empty.py", "")
    assert isinstance(result.issues, list)
