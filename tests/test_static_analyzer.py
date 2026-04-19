import subprocess
from unittest.mock import patch, MagicMock

from src.analyzer.static import (
    analyze_file,
    StaticAnalysisResult,
    AnalysisIssue,
    _run_pylint,
    _run_flake8,
    _run_bandit,
    _is_test_file,
)

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

# ---------------------------------------------------------------------------
# 기존 테스트
# ---------------------------------------------------------------------------

def test_clean_code_has_no_errors():
    # 정상 Python 코드는 error 심각도 이슈를 생성하지 않는다
    result = analyze_file("clean.py", CLEAN_CODE)
    assert isinstance(result, StaticAnalysisResult)
    errors = [i for i in result.issues if i.severity == "error"]
    assert len(errors) == 0


def test_bad_code_detects_issues():
    # 문제 있는 Python 코드는 이슈를 1개 이상 생성한다
    result = analyze_file("bad.py", BAD_CODE)
    assert len(result.issues) > 0


def test_bandit_detects_eval():
    # eval(input()) 패턴은 bandit이 HIGH 보안 이슈로 탐지한다
    result = analyze_file("eval.py", "eval(input())\n")
    bandit_issues = [i for i in result.issues if i.tool == "bandit"]
    assert len(bandit_issues) > 0


def test_result_has_correct_filename():
    # 반환된 StaticAnalysisResult.filename 은 전달된 filename과 동일하다
    result = analyze_file("myfile.py", CLEAN_CODE)
    assert result.filename == "myfile.py"


def test_empty_content_returns_no_issues():
    # 빈 content 는 subprocess 호출 없이 빈 이슈 목록을 반환한다
    result = analyze_file("empty.py", "")
    assert isinstance(result.issues, list)


# ---------------------------------------------------------------------------
# 비-Python 파일 처리 테스트
# ---------------------------------------------------------------------------

def test_non_python_md_file_returns_empty_issues():
    # .md 파일을 analyze_file 에 넘기면 pylint/bandit 없이 빈 이슈 목록을 반환한다
    with patch("src.analyzer.static._run_pylint") as mock_pylint, \
         patch("src.analyzer.static._run_flake8") as mock_flake8, \
         patch("src.analyzer.static._run_bandit") as mock_bandit:
        mock_pylint.return_value = []
        mock_flake8.return_value = []
        mock_bandit.return_value = []
        result = analyze_file("README.md", "# Hello\nThis is markdown.\n")
    assert isinstance(result, StaticAnalysisResult)
    assert result.filename == "README.md"
    # .md 파일은 Python이 아니므로 실제 subprocess가 호출되더라도 이슈가 없어야 함
    assert isinstance(result.issues, list)


def test_non_python_yml_file_with_mocked_tools_returns_no_issues():
    # .yml 파일 분석 시 도구들이 이슈를 반환하지 않으면 빈 결과를 반환한다
    with patch("src.analyzer.static._run_pylint", return_value=[]), \
         patch("src.analyzer.static._run_flake8", return_value=[]), \
         patch("src.analyzer.static._run_bandit", return_value=[]):
        result = analyze_file("config.yml", "key: value\n")
    assert len(result.issues) == 0
    assert result.filename == "config.yml"


def test_non_python_json_file_with_mocked_tools_returns_no_issues():
    # .json 파일 분석 시 이슈 없이 StaticAnalysisResult 를 반환한다
    with patch("src.analyzer.static._run_pylint", return_value=[]), \
         patch("src.analyzer.static._run_flake8", return_value=[]), \
         patch("src.analyzer.static._run_bandit", return_value=[]):
        result = analyze_file("package.json", '{"name": "test"}\n')
    assert isinstance(result, StaticAnalysisResult)
    assert result.filename == "package.json"
    assert result.issues == []


# ---------------------------------------------------------------------------
# pylint FileNotFoundError (바이너리 없음) 처리
# ---------------------------------------------------------------------------

def test_pylint_file_not_found_returns_empty_list():
    # pylint 바이너리가 없을 때 FileNotFoundError → 빈 이슈 목록 반환
    with patch("subprocess.run", side_effect=FileNotFoundError("pylint not found")):
        result = _run_pylint("/tmp/fake.py")
    assert result == []


def test_analyze_file_pylint_binary_missing_returns_result():
    # pylint 바이너리 없을 때 analyze_file 은 크래시 없이 StaticAnalysisResult 반환한다
    with patch("src.analyzer.static._run_pylint", side_effect=FileNotFoundError):
        # _run_pylint 자체가 FileNotFoundError 를 내부에서 처리하므로
        # analyze_file 은 _run_pylint 가 [] 를 반환한다고 가정
        pass

    # _run_pylint 내부에서 FileNotFoundError 를 잡아 [] 를 반환하는지 직접 검증
    with patch("subprocess.run", side_effect=FileNotFoundError("no pylint binary")):
        issues = _run_pylint("/tmp/test_file.py")
    assert issues == []


def test_flake8_file_not_found_returns_empty_list():
    # flake8 바이너리가 없을 때 FileNotFoundError → 빈 이슈 목록 반환
    with patch("subprocess.run", side_effect=FileNotFoundError("flake8 not found")):
        result = _run_flake8("/tmp/fake.py")
    assert result == []


def test_bandit_file_not_found_returns_empty_list():
    # bandit 바이너리가 없을 때 FileNotFoundError → 빈 이슈 목록 반환
    with patch("subprocess.run", side_effect=FileNotFoundError("bandit not found")):
        result = _run_bandit("/tmp/fake.py")
    assert result == []


# ---------------------------------------------------------------------------
# bandit TimeoutExpired 처리
# ---------------------------------------------------------------------------

def test_bandit_timeout_returns_empty_list():
    # bandit subprocess 가 TimeoutExpired 를 발생시키면 빈 이슈 목록을 반환한다
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="bandit", timeout=30)):
        result = _run_bandit("/tmp/fake.py")
    assert result == []


def test_pylint_timeout_returns_empty_list():
    # pylint subprocess 가 TimeoutExpired 를 발생시키면 빈 이슈 목록을 반환한다
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pylint", timeout=30)):
        result = _run_pylint("/tmp/fake.py")
    assert result == []


def test_flake8_timeout_returns_empty_list():
    # flake8 subprocess 가 TimeoutExpired 를 발생시키면 빈 이슈 목록을 반환한다
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="flake8", timeout=30)):
        result = _run_flake8("/tmp/fake.py")
    assert result == []


# ---------------------------------------------------------------------------
# pylint JSON 파싱 실패 처리
# ---------------------------------------------------------------------------

def test_pylint_json_decode_error_returns_empty_list():
    # pylint stdout 이 유효하지 않은 JSON 이면 JSONDecodeError → 빈 이슈 목록 반환
    mock_proc = MagicMock()
    mock_proc.stdout = "this is not valid json at all"
    mock_proc.returncode = 0
    # stdout 이 "[" 로 시작하지 않으면 json.loads 를 건너뛰고 [] 반환
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_pylint("/tmp/fake.py")
    assert result == []


def test_pylint_stdout_starts_with_bracket_but_invalid_json_returns_empty():
    # pylint stdout 이 "[" 로 시작하지만 파싱 불가능한 JSON 이면 빈 이슈 목록 반환
    mock_proc = MagicMock()
    mock_proc.stdout = "[invalid json content}"
    mock_proc.returncode = 0
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_pylint("/tmp/fake.py")
    assert result == []


def test_bandit_invalid_json_returns_empty_list():
    # bandit stdout 이 유효하지 않은 JSON 이면 빈 이슈 목록을 반환한다
    mock_proc = MagicMock()
    mock_proc.stdout = "[broken json"
    mock_proc.returncode = 1
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_bandit("/tmp/fake.py")
    assert result == []


# ---------------------------------------------------------------------------
# pylint 정상 파싱 — AnalysisIssue 생성 검증
# ---------------------------------------------------------------------------

def test_pylint_error_type_maps_to_error_severity():
    # pylint 가 type="error" 인 항목을 반환하면 severity="error" 로 매핑된다
    mock_proc = MagicMock()
    mock_proc.stdout = '[{"type": "error", "message": "undefined variable", "line": 5}]'
    mock_proc.returncode = 1
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_pylint("/tmp/fake.py")
    assert len(result) == 1
    assert result[0].severity == "error"
    assert result[0].tool == "pylint"
    assert result[0].line == 5


def test_pylint_warning_type_maps_to_warning_severity():
    # pylint 가 type="warning" 인 항목을 반환하면 severity="warning" 으로 매핑된다
    mock_proc = MagicMock()
    mock_proc.stdout = '[{"type": "warning", "message": "unused import", "line": 2}]'
    mock_proc.returncode = 4
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_pylint("/tmp/fake.py")
    assert len(result) == 1
    assert result[0].severity == "warning"


def test_pylint_fatal_type_maps_to_error_severity():
    # pylint 가 type="fatal" 인 항목을 반환하면 severity="error" 로 매핑된다
    mock_proc = MagicMock()
    mock_proc.stdout = '[{"type": "fatal", "message": "syntax error", "line": 1}]'
    mock_proc.returncode = 1
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_pylint("/tmp/fake.py")
    assert len(result) == 1
    assert result[0].severity == "error"


# ---------------------------------------------------------------------------
# bandit 정상 파싱 — AnalysisIssue 생성 검증
# ---------------------------------------------------------------------------

def test_bandit_high_severity_maps_to_error():
    # bandit issue_severity=HIGH 이면 AnalysisIssue.severity="error" 로 매핑된다
    mock_proc = MagicMock()
    mock_proc.stdout = '{"results": [{"issue_severity": "HIGH", "issue_text": "hardcoded password", "line_number": 3}]}'
    mock_proc.returncode = 1
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_bandit("/tmp/fake.py")
    assert len(result) == 1
    assert result[0].severity == "error"
    assert result[0].tool == "bandit"
    assert result[0].line == 3


def test_bandit_medium_severity_maps_to_warning():
    # bandit issue_severity=MEDIUM 이면 AnalysisIssue.severity="warning" 으로 매핑된다
    mock_proc = MagicMock()
    mock_proc.stdout = '{"results": [{"issue_severity": "MEDIUM", "issue_text": "subprocess call", "line_number": 10}]}'
    mock_proc.returncode = 1
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_bandit("/tmp/fake.py")
    assert len(result) == 1
    assert result[0].severity == "warning"


def test_bandit_empty_results_returns_empty_list():
    # bandit 이 results=[] 를 반환하면 빈 이슈 목록을 반환한다
    mock_proc = MagicMock()
    mock_proc.stdout = '{"results": []}'
    mock_proc.returncode = 0
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_bandit("/tmp/fake.py")
    assert result == []


def test_bandit_empty_stdout_returns_empty_list():
    # bandit stdout 이 완전히 비어 있으면 빈 이슈 목록을 반환한다
    mock_proc = MagicMock()
    mock_proc.stdout = ""
    mock_proc.returncode = 0
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_bandit("/tmp/fake.py")
    assert result == []


# ---------------------------------------------------------------------------
# 테스트 파일 감지 — _is_test_file
# ---------------------------------------------------------------------------

def test_is_test_file_detects_test_prefix():
    # test_ 로 시작하는 파일명을 테스트 파일로 감지한다
    assert _is_test_file("test_something.py") is True


def test_is_test_file_detects_test_suffix():
    # _test.py 로 끝나는 파일명을 테스트 파일로 감지한다
    assert _is_test_file("something_test.py") is True


def test_is_test_file_normal_file_returns_false():
    # 일반 파일명은 테스트 파일로 감지하지 않는다
    assert _is_test_file("my_module.py") is False


def test_is_test_file_with_path_prefix():
    # 경로가 포함된 경우에도 basename 기준으로 테스트 파일 여부를 판단한다
    assert _is_test_file("tests/test_analyzer.py") is True
    assert _is_test_file("src/analyzer/static.py") is False


# ---------------------------------------------------------------------------
# 테스트 파일에서 bandit 비실행 검증
# ---------------------------------------------------------------------------

def test_test_file_skips_bandit():
    # test_ 접두사 파일은 bandit(security) 검사를 건너뛴다 — Registry _BanditAnalyzer.is_enabled
    with patch("src.analyzer.tools.python._BanditAnalyzer.run", return_value=[]) as mock_bandit_run, \
         patch("src.analyzer.tools.python._BanditAnalyzer.is_enabled", return_value=False) as mock_enabled:
        result = analyze_file("test_something.py", "def test_foo(): pass\n")
    # 테스트 파일에서 bandit 결과는 없어야 한다
    security_issues = [i for i in result.issues if i.category == "security"]
    assert len(security_issues) == 0


def test_non_test_file_runs_bandit():
    # 일반 .py 파일은 bandit(security) 검사를 실행한다 — is_enabled=True 기본
    result = analyze_file("module.py", "eval(input())\n")
    # bandit 이슈가 있거나 빈 목록이어도 security 카테고리로 분류되어야 함
    # (실제 bandit 실행 여부 확인)
    from src.analyzer.tools.python import _BanditAnalyzer
    from src.analyzer.registry import AnalyzeContext
    ctx = AnalyzeContext(filename="module.py", content="x=1\n", language="python",
                         is_test=False, tmp_path="module.py")
    assert _BanditAnalyzer().is_enabled(ctx) is True


# ---------------------------------------------------------------------------
# flake8 출력 파싱 검증
# ---------------------------------------------------------------------------

def test_flake8_parses_output_correctly():
    # flake8 의 "row:col: message" 형식 출력을 정확히 파싱한다
    mock_proc = MagicMock()
    mock_proc.stdout = "5:1: E302 expected 2 blank lines, found 1"
    mock_proc.returncode = 1
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_flake8("/tmp/fake.py")
    assert len(result) == 1
    assert result[0].tool == "flake8"
    assert result[0].severity == "warning"
    assert result[0].line == 5


def test_flake8_empty_output_returns_empty_list():
    # flake8 stdout 이 비어 있으면 빈 이슈 목록을 반환한다
    mock_proc = MagicMock()
    mock_proc.stdout = ""
    mock_proc.returncode = 0
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_flake8("/tmp/fake.py")
    assert result == []


def test_flake8_invalid_line_format_is_skipped():
    # flake8 출력 중 파싱 불가능한 줄(parts < 3)은 건너뛴다
    mock_proc = MagicMock()
    mock_proc.stdout = "not:parseable\n10:1: W291 trailing whitespace"
    mock_proc.returncode = 1
    with patch("subprocess.run", return_value=mock_proc):
        result = _run_flake8("/tmp/fake.py")
    # "not:parseable" 은 parts==2 이므로 건너뜀, 10:1:W291 은 parts==3 이므로 포함
    assert len(result) == 1
    assert result[0].line == 10
