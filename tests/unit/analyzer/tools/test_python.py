"""Phase 4 PR-T1 — Python static analyzer tools 단위 테스트.

대상 모듈: `src/analyzer/io/tools/python.py`
  - _PylintAnalyzer  (code_quality)
  - _Flake8Analyzer  (code_quality)
  - _BanditAnalyzer  (security, 테스트 파일 제외)

subprocess.run mock 으로 실제 도구 바이너리 호출 없이 모든 경로 검증.
14-에이전트 감사 R1-B 에서 식별된 Critical Gap (test_python.py 전무) 해소.
"""
import json
import os
import subprocess

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-github-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-github-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

# pylint: disable=redefined-outer-name,wrong-import-position
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer.io.tools.python import (
    _BanditAnalyzer,
    _Flake8Analyzer,
    _PylintAnalyzer,
)
from src.analyzer.pure.registry import (
    AnalyzeContext,
    Category,
    Severity,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT


# ──────────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — subprocess.run mock + AnalyzeContext fixture
# ──────────────────────────────────────────────────────────────────────────


def _mock_proc(stdout: str = "", returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값을 모방하는 MagicMock 생성."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


@pytest.fixture
def py_ctx() -> AnalyzeContext:
    """Python 파일용 AnalyzeContext (테스트 아님)."""
    return AnalyzeContext(
        filename="src/example.py",
        content="x = 1\n",
        language="python",
        tmp_path="/tmp/example.py",
        is_test=False,
    )


@pytest.fixture
def py_test_ctx() -> AnalyzeContext:
    """Python 테스트 파일용 AnalyzeContext."""
    return AnalyzeContext(
        filename="tests/test_example.py",
        content="def test_foo(): pass\n",
        language="python",
        tmp_path="/tmp/test_example.py",
        is_test=True,
    )


@pytest.fixture
def js_ctx() -> AnalyzeContext:
    """JavaScript 파일 — Python analyzer가 supports() 거부해야 함."""
    return AnalyzeContext(
        filename="src/app.js",
        content="const x = 1;\n",
        language="javascript",
        tmp_path="/tmp/app.js",
        is_test=False,
    )


# ──────────────────────────────────────────────────────────────────────────
# _PylintAnalyzer
# ──────────────────────────────────────────────────────────────────────────


class TestPylintAnalyzerAttributes:
    """name/category 속성 + Analyzer Protocol 구현 검증."""

    def test_name_is_pylint(self):
        assert _PylintAnalyzer().name == "pylint"

    def test_category_is_code_quality(self):
        assert _PylintAnalyzer().category == Category.CODE_QUALITY


class TestPylintSupports:
    """supports(): language=='python' 만 True."""

    def test_returns_true_for_python(self, py_ctx):
        assert _PylintAnalyzer().supports(py_ctx) is True

    def test_returns_false_for_javascript(self, js_ctx):
        assert _PylintAnalyzer().supports(js_ctx) is False

    @pytest.mark.parametrize("lang", ["go", "rust", "shell", "ruby", "unknown"])
    def test_returns_false_for_other_languages(self, lang):
        ctx = AnalyzeContext(
            filename="x", content="", language=lang,
            tmp_path="/tmp/x", is_test=False,
        )
        assert _PylintAnalyzer().supports(ctx) is False


class TestPylintIsEnabled:
    """is_enabled(): 항상 True (pip 의존성 보장)."""

    def test_always_enabled_for_prod(self, py_ctx):
        assert _PylintAnalyzer().is_enabled(py_ctx) is True

    def test_always_enabled_for_test(self, py_test_ctx):
        assert _PylintAnalyzer().is_enabled(py_test_ctx) is True


class TestPylintRunSubprocessCall:
    """subprocess.run 호출 인자 검증."""

    def test_includes_pylint_binary_and_path(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "pylint"
        assert "/tmp/example.py" in cmd

    def test_uses_static_analysis_timeout(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        assert mock_run.call_args.kwargs["timeout"] == STATIC_ANALYSIS_TIMEOUT

    def test_includes_json_output_format(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert "--output-format=json" in cmd

    def test_test_file_adds_extra_disables(self, py_test_ctx):
        """is_test=True → W0611,W0212,C0302,R0401 추가 disable."""
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_test_ctx)
        cmd = mock_run.call_args.args[0]
        disable_arg = next(a for a in cmd if a.startswith("--disable="))
        assert "W0611" in disable_arg
        assert "R0401" in disable_arg

    def test_prod_file_no_extra_test_disables(self, py_ctx):
        """is_test=False → W0611 등 미포함."""
        with patch("subprocess.run", return_value=_mock_proc("[]")) as mock_run:
            _PylintAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        disable_arg = next(a for a in cmd if a.startswith("--disable="))
        assert "W0611" not in disable_arg


class TestPylintRunOutputParsing:
    """JSON 출력 파싱 + Severity 분류."""

    def test_maps_error_type_to_error_severity(self, py_ctx):
        stdout = json.dumps([
            {"type": "error", "message": "undefined name", "line": 5},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].tool == "pylint"
        assert issues[0].line == 5
        assert issues[0].category == Category.CODE_QUALITY

    def test_maps_fatal_type_to_error_severity(self, py_ctx):
        stdout = json.dumps([
            {"type": "fatal", "message": "fatal error", "line": 1},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.ERROR

    def test_maps_warning_type_to_warning_severity(self, py_ctx):
        stdout = json.dumps([
            {"type": "warning", "message": "unused var", "line": 3},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_maps_convention_type_to_warning_severity(self, py_ctx):
        """convention/refactor/info 등 비-error 타입은 모두 WARNING."""
        stdout = json.dumps([
            {"type": "convention", "message": "naming", "line": 1},
        ])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_returns_empty_when_stdout_not_starts_with_bracket(self, py_ctx):
        """non-JSON stdout (예: pylint banner) → 빈 list."""
        with patch("subprocess.run", return_value=_mock_proc("Your code rated 10.00/10")):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues == []

    def test_returns_empty_when_stdout_empty(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("")):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues == []

    def test_propagates_language_field(self, py_ctx):
        stdout = json.dumps([{"type": "warning", "message": "x", "line": 1}])
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues[0].language == "python"


class TestPylintRunGracefulDegradation:
    """예외 상황 graceful fallback 검증."""

    def test_timeout_returns_empty_list(self, py_ctx, caplog):
        import logging
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="pylint", timeout=30),
        ):
            with caplog.at_level(logging.WARNING):
                issues = _PylintAnalyzer().run(py_ctx)
        assert issues == []
        assert any("pylint timed out" in r.message for r in caplog.records)

    def test_file_not_found_returns_empty(self, py_ctx):
        """pylint 미설치 시 FileNotFoundError → []."""
        with patch("subprocess.run", side_effect=FileNotFoundError("pylint not installed")):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues == []

    def test_json_decode_error_returns_empty(self, py_ctx):
        """깨진 JSON ([로 시작하지만 파싱 실패) → []."""
        with patch("subprocess.run", return_value=_mock_proc("[broken json")):
            issues = _PylintAnalyzer().run(py_ctx)
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────
# _Flake8Analyzer
# ──────────────────────────────────────────────────────────────────────────


class TestFlake8AnalyzerAttributes:
    def test_name_is_flake8(self):
        assert _Flake8Analyzer().name == "flake8"

    def test_category_is_code_quality(self):
        assert _Flake8Analyzer().category == Category.CODE_QUALITY


class TestFlake8Supports:
    def test_supports_python(self, py_ctx):
        assert _Flake8Analyzer().supports(py_ctx) is True

    def test_rejects_javascript(self, js_ctx):
        assert _Flake8Analyzer().supports(js_ctx) is False


class TestFlake8IsEnabled:
    def test_always_enabled(self, py_ctx, py_test_ctx):
        assert _Flake8Analyzer().is_enabled(py_ctx) is True
        assert _Flake8Analyzer().is_enabled(py_test_ctx) is True


class TestFlake8RunSubprocessCall:
    def test_includes_flake8_binary(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("")) as mock_run:
            _Flake8Analyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "flake8"

    def test_includes_max_line_length(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("")) as mock_run:
            _Flake8Analyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert "--max-line-length=120" in cmd

    def test_test_file_adds_ignore_flag(self, py_test_ctx):
        """is_test=True → --ignore=E302,E402,... 추가."""
        with patch("subprocess.run", return_value=_mock_proc("")) as mock_run:
            _Flake8Analyzer().run(py_test_ctx)
        cmd = mock_run.call_args.args[0]
        ignore_args = [a for a in cmd if a.startswith("--ignore=")]
        assert ignore_args
        assert "F401" in ignore_args[0]


class TestFlake8RunOutputParsing:
    def test_parses_row_col_text_format(self, py_ctx):
        stdout = "10:5: E501 line too long\n3:1: F401 unused import\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _Flake8Analyzer().run(py_ctx)
        assert len(issues) == 2
        assert issues[0].line == 10
        assert "E501" in issues[0].message
        assert issues[1].line == 3
        assert all(i.severity == Severity.WARNING for i in issues)

    def test_skips_malformed_lines(self, py_ctx):
        """parts.split(':',2) 결과 길이 != 3 → continue (skip)."""
        stdout = "totally invalid line\n5:2: valid issue\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _Flake8Analyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].line == 5

    def test_skips_value_error_on_int_parse(self, py_ctx):
        """int(parts[0]) 실패 시 continue."""
        stdout = "abc:def: not a number\n7:3: valid\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _Flake8Analyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].line == 7

    def test_returns_empty_for_empty_stdout(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("")):
            issues = _Flake8Analyzer().run(py_ctx)
        assert issues == []


class TestFlake8RunGracefulDegradation:
    def test_timeout_returns_empty(self, py_ctx, caplog):
        import logging
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="flake8", timeout=30),
        ):
            with caplog.at_level(logging.WARNING):
                issues = _Flake8Analyzer().run(py_ctx)
        assert issues == []
        assert any("flake8 timed out" in r.message for r in caplog.records)

    def test_file_not_found_returns_empty(self, py_ctx):
        with patch("subprocess.run", side_effect=FileNotFoundError("flake8 not installed")):
            issues = _Flake8Analyzer().run(py_ctx)
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────
# _BanditAnalyzer
# ──────────────────────────────────────────────────────────────────────────


class TestBanditAnalyzerAttributes:
    def test_name_is_bandit(self):
        assert _BanditAnalyzer().name == "bandit"

    def test_category_is_security(self):
        assert _BanditAnalyzer().category == Category.SECURITY


class TestBanditSupports:
    def test_supports_python(self, py_ctx):
        assert _BanditAnalyzer().supports(py_ctx) is True

    def test_rejects_javascript(self, js_ctx):
        assert _BanditAnalyzer().supports(js_ctx) is False


class TestBanditIsEnabled:
    """bandit 은 테스트 파일 제외 (프로덕션 코드만)."""

    def test_enabled_for_prod_files(self, py_ctx):
        assert _BanditAnalyzer().is_enabled(py_ctx) is True

    def test_disabled_for_test_files(self, py_test_ctx):
        assert _BanditAnalyzer().is_enabled(py_test_ctx) is False


class TestBanditRunSubprocessCall:
    def test_includes_bandit_binary_and_json_format(self, py_ctx):
        stdout = json.dumps({"results": []})
        with patch("subprocess.run", return_value=_mock_proc(stdout)) as mock_run:
            _BanditAnalyzer().run(py_ctx)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "bandit"
        assert "-f" in cmd
        assert "json" in cmd
        assert "/tmp/example.py" in cmd


class TestBanditRunOutputParsing:
    def test_maps_high_severity_to_error(self, py_ctx):
        stdout = json.dumps({"results": [
            {
                "issue_severity": "HIGH",
                "issue_text": "use of subprocess shell=True",
                "line_number": 12,
            },
        ]})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR
        assert issues[0].tool == "bandit"
        assert issues[0].line == 12
        assert issues[0].category == Category.SECURITY

    def test_maps_low_severity_to_warning(self, py_ctx):
        stdout = json.dumps({"results": [
            {"issue_severity": "LOW", "issue_text": "weak rng", "line_number": 5},
        ]})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_maps_medium_severity_to_warning(self, py_ctx):
        stdout = json.dumps({"results": [
            {"issue_severity": "MEDIUM", "issue_text": "x", "line_number": 1},
        ]})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues[0].severity == Severity.WARNING

    def test_returns_empty_when_results_key_missing(self, py_ctx):
        """results 키 없는 정상 JSON → 빈 list (graceful)."""
        stdout = json.dumps({"errors": [], "metrics": {}})
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []

    def test_returns_empty_when_stdout_not_json(self, py_ctx):
        """stdout 이 { 로 시작하지 않으면 빈 list."""
        with patch("subprocess.run", return_value=_mock_proc("bandit usage info")):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []


class TestBanditRunGracefulDegradation:
    def test_timeout_returns_empty(self, py_ctx, caplog):
        import logging
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="bandit", timeout=30),
        ):
            with caplog.at_level(logging.WARNING):
                issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []
        assert any("bandit timed out" in r.message for r in caplog.records)

    def test_file_not_found_returns_empty(self, py_ctx):
        with patch("subprocess.run", side_effect=FileNotFoundError("bandit not installed")):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []

    def test_json_decode_error_returns_empty(self, py_ctx):
        with patch("subprocess.run", return_value=_mock_proc("{broken json")):
            issues = _BanditAnalyzer().run(py_ctx)
        assert issues == []
