"""TDD Red 상태 테스트 — Phase C: ShellCheck Analyzer.

신설 대상:
  src/analyzer/tools/shellcheck.py  — _ShellCheckAnalyzer (Analyzer Protocol 구현)

ShellCheck는 shell 스크립트 파일의 코드 품질 분석을 담당한다.
subprocess.run mock으로 실제 shellcheck 바이너리 호출 없이 모든 경로를 검증한다.
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

import pytest
from unittest.mock import patch, MagicMock


# ──────────────────────────────────────────────────────────────────────────────
# REGISTRY 격리 픽스처 — 각 테스트 실행 전후 REGISTRY를 원래 상태로 복원한다.
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_registry():
    """테스트 간 REGISTRY 오염 방지 — 테스트 전후 REGISTRY를 격리한다."""
    try:
        import src.analyzer.io.tools.python  # noqa: F401 — Python 도구 먼저 등록
        from src.analyzer.pure.registry import REGISTRY
        original = list(REGISTRY)
        REGISTRY.clear()
        yield
        REGISTRY.clear()
        REGISTRY.extend(original)
    except ImportError:
        # registry.py 미생성 상태(Red)에서도 다른 테스트가 실행되도록 허용
        yield


# ──────────────────────────────────────────────────────────────────────────────
# 공용 헬퍼 — shellcheck subprocess mock 생성
# ──────────────────────────────────────────────────────────────────────────────

def _mock_shellcheck_proc(stdout: str, returncode: int = 0) -> MagicMock:
    """subprocess.run 반환값을 모방하는 MagicMock을 생성한다."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    return mock


# ShellCheck JSON 출력 샘플 — error + warning 혼합
SAMPLE_SHELLCHECK_OUTPUT = json.dumps([
    {
        "file": "test.sh",
        "line": 5,
        "column": 1,
        "level": "error",
        "code": 1234,
        "message": "Double quote to prevent globbing and word splitting.",
    },
    {
        "file": "test.sh",
        "line": 12,
        "column": 3,
        "level": "warning",
        "code": 2006,
        "message": "Use $(...) notation instead of legacy backtick.",
    },
])

# ShellCheck JSON 출력 샘플 — error만 포함
SAMPLE_OUTPUT_ERROR_ONLY = json.dumps([
    {
        "file": "deploy.sh",
        "line": 8,
        "column": 1,
        "level": "error",
        "code": 1091,
        "message": "Not following: ./lib.sh was not specified as input.",
    },
])

# ShellCheck JSON 출력 샘플 — warning만 포함
SAMPLE_OUTPUT_WARNING_ONLY = json.dumps([
    {
        "file": "setup.sh",
        "line": 20,
        "column": 5,
        "level": "warning",
        "code": 2086,
        "message": "Double quote to prevent globbing and word splitting.",
    },
])

# ShellCheck JSON 출력 샘플 — info 레벨 포함
SAMPLE_OUTPUT_INFO = json.dumps([
    {
        "file": "check.sh",
        "line": 3,
        "column": 1,
        "level": "info",
        "code": 2164,
        "message": "Use 'cd ... || exit' or 'cd ... || return' in case cd fails.",
    },
])

# ShellCheck JSON 출력 샘플 — style 레벨 포함
SAMPLE_OUTPUT_STYLE = json.dumps([
    {
        "file": "script.sh",
        "line": 7,
        "column": 2,
        "level": "style",
        "code": 2250,
        "message": "Prefer putting braces around variable references.",
    },
])

# ShellCheck JSON 출력 샘플 — 빈 배열
SAMPLE_OUTPUT_EMPTY = json.dumps([])

# ShellCheck JSON 출력 샘플 — 모든 레벨 혼합 (error/warning/info/style)
SAMPLE_OUTPUT_ALL_LEVELS = json.dumps([
    {"file": "all.sh", "line": 1, "column": 1, "level": "error", "code": 1001, "message": "error msg"},
    {"file": "all.sh", "line": 2, "column": 1, "level": "warning", "code": 2001, "message": "warning msg"},
    {"file": "all.sh", "line": 3, "column": 1, "level": "info", "code": 2164, "message": "info msg"},
    {"file": "all.sh", "line": 4, "column": 1, "level": "style", "code": 2250, "message": "style msg"},
])


# ──────────────────────────────────────────────────────────────────────────────
# 픽스처 — AnalyzeContext 생성 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def make_ctx():
    """언어와 파일명을 받아 AnalyzeContext를 생성하는 팩토리 픽스처."""
    from src.analyzer.pure.registry import AnalyzeContext

    def _factory(language: str, filename: str = "test_script.sh",
                 is_test: bool = False, tmp_path: str = "/tmp/test_script.sh"):
        return AnalyzeContext(
            filename=filename,
            content="#!/bin/bash\necho hello\n",
            language=language,
            is_test=is_test,
            tmp_path=tmp_path,
        )
    return _factory


# ──────────────────────────────────────────────────────────────────────────────
# TestShellCheckAnalyzerAttributes — 클래스 속성 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestShellCheckAnalyzerAttributes:
    def test_name_is_shellcheck(self):
        # _ShellCheckAnalyzer.name은 "shellcheck"이어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        assert _ShellCheckAnalyzer().name == "shellcheck"

    def test_category_is_code_quality(self):
        # _ShellCheckAnalyzer.category는 "code_quality"이어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        assert _ShellCheckAnalyzer().category == "code_quality"

    def test_supported_languages_is_frozenset(self):
        # SUPPORTED_LANGUAGES는 frozenset 타입이어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        assert isinstance(_ShellCheckAnalyzer.SUPPORTED_LANGUAGES, frozenset)

    def test_supported_languages_contains_shell(self):
        # SUPPORTED_LANGUAGES에 "shell"이 포함되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        assert "shell" in _ShellCheckAnalyzer.SUPPORTED_LANGUAGES


# ──────────────────────────────────────────────────────────────────────────────
# TestShellCheckSupports — supports() 언어별 반환값 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestShellCheckSupports:
    def test_supports_returns_true_for_shell(self, make_ctx):
        # shell 파일에서 supports()는 True를 반환해야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell")
        assert _ShellCheckAnalyzer().supports(ctx) is True

    @pytest.mark.parametrize("language", [
        "python", "javascript", "unknown", "go", "typescript",
    ])
    def test_supports_returns_false_for_non_shell_languages(self, language, make_ctx):
        # shell 외 언어에서 supports()는 False를 반환해야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language=language)
        assert _ShellCheckAnalyzer().supports(ctx) is False


# ──────────────────────────────────────────────────────────────────────────────
# TestShellCheckIsEnabled — is_enabled() shellcheck 바이너리 존재 여부 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestShellCheckIsEnabled:
    def test_is_enabled_returns_true_when_shellcheck_binary_exists(self, make_ctx):
        # shutil.which("shellcheck")이 경로를 반환하면 is_enabled()는 True를 반환한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell")
        with patch("shutil.which", return_value="/usr/bin/shellcheck"):
            assert _ShellCheckAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_returns_false_when_shellcheck_binary_missing(self, make_ctx):
        # shutil.which("shellcheck")이 None을 반환하면 is_enabled()는 False를 반환한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell")
        with patch("shutil.which", return_value=None):
            assert _ShellCheckAnalyzer().is_enabled(ctx) is False

    def test_is_enabled_checks_shellcheck_binary_specifically(self, make_ctx):
        # is_enabled()가 shutil.which를 "shellcheck" 인자로 호출하는지 검증한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell")
        with patch("shutil.which", return_value="/usr/bin/shellcheck") as mock_which:
            _ShellCheckAnalyzer().is_enabled(ctx)
        mock_which.assert_called_once_with("shellcheck")


# ──────────────────────────────────────────────────────────────────────────────
# TestShellCheckRunSubprocessCall — subprocess 호출 인자 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestShellCheckRunSubprocessCall:
    def test_run_includes_format_json_flag(self, make_ctx):
        # shellcheck 실행 시 "-f" "json" 플래그가 포함되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/script.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_EMPTY)) as mock_run:
            _ShellCheckAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        # "-f json" 또는 "--format=json" 또는 "-f", "json" 형태 모두 허용
        cmd_str = " ".join(call_args)
        assert "-f json" in cmd_str or "--format=json" in cmd_str or (
            "-f" in call_args and "json" in call_args
        )

    def test_run_passes_tmp_path_to_shellcheck(self, make_ctx):
        # shellcheck 실행 시 ctx.tmp_path가 인자에 포함되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/specific_script.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_EMPTY)) as mock_run:
            _ShellCheckAnalyzer().run(ctx)
        call_args = mock_run.call_args[0][0]
        assert "/tmp/specific_script.sh" in call_args


# ──────────────────────────────────────────────────────────────────────────────
# TestShellCheckRunOutputParsing — run() JSON 출력 파싱 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestShellCheckRunOutputParsing:
    def test_run_maps_level_error_to_severity_error(self, make_ctx):
        # ShellCheck level "error"는 AnalysisIssue.severity="error"로 매핑되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/deploy.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_run_maps_level_warning_to_severity_warning(self, make_ctx):
        # ShellCheck level "warning"은 AnalysisIssue.severity="warning"으로 매핑되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/setup.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_WARNING_ONLY)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "warning"

    def test_run_maps_level_info_to_severity_warning(self, make_ctx):
        # ShellCheck level "info"는 AnalysisIssue.severity="warning"으로 하향 매핑되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/check.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_INFO)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "warning"

    def test_run_maps_level_style_to_severity_warning(self, make_ctx):
        # ShellCheck level "style"은 AnalysisIssue.severity="warning"으로 하향 매핑되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/script.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_STYLE)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == "warning"

    def test_run_parses_multiple_issues_correctly(self, make_ctx):
        # 복수 이슈가 포함된 출력에서 모든 이슈를 반환해야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/test.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_SHELLCHECK_OUTPUT)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert len(issues) == 2
        severities = {i.severity for i in issues}
        assert "error" in severities
        assert "warning" in severities

    def test_run_returns_empty_list_for_empty_array_output(self, make_ctx):
        # shellcheck가 [] (빈 배열) 출력 → 빈 이슈 목록을 반환해야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/clean.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_EMPTY)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_list_for_empty_stdout(self, make_ctx):
        # stdout이 빈 문자열이면 빈 이슈 목록을 반환해야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/script.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc("")):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues == []

    def test_run_sets_tool_name_to_shellcheck(self, make_ctx):
        # 모든 AnalysisIssue.tool 값은 "shellcheck"이어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/deploy.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues[0].tool == "shellcheck"

    def test_run_sets_language_from_ctx(self, make_ctx):
        # AnalysisIssue.language는 ctx.language 값("shell")으로 설정되어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/deploy.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues[0].language == "shell"

    def test_run_sets_category_to_code_quality(self, make_ctx):
        # 모든 ShellCheck 이슈의 category는 "code_quality"이어야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/test.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_SHELLCHECK_OUTPUT)):
            issues = _ShellCheckAnalyzer().run(ctx)
        for issue in issues:
            assert issue.category == "code_quality"

    def test_run_sets_line_number_from_output(self, make_ctx):
        # AnalysisIssue.line은 shellcheck JSON의 line 필드에서 가져와야 한다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/deploy.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_ERROR_ONLY)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues[0].line == 8

    def test_run_all_four_levels_produce_correct_severities(self, make_ctx):
        # error→error, warning/info/style→warning 레벨 매핑이 한 번에 검증된다
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/all.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc(SAMPLE_OUTPUT_ALL_LEVELS)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert len(issues) == 4
        # line 1 → error
        error_issues = [i for i in issues if i.line == 1]
        assert error_issues[0].severity == "error"
        # line 2,3,4 → warning
        non_error_issues = [i for i in issues if i.line != 1]
        for issue in non_error_issues:
            assert issue.severity == "warning"


# ──────────────────────────────────────────────────────────────────────────────
# TestShellCheckRunGracefulDegradation — 예외 상황에서 graceful 반환 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestShellCheckRunGracefulDegradation:
    def test_run_returns_empty_on_file_not_found_error(self, make_ctx):
        # shellcheck 바이너리가 없어서 FileNotFoundError 발생 → 빈 이슈 목록 반환 (파이프라인 미중단)
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/script.sh")
        with patch("subprocess.run", side_effect=FileNotFoundError("shellcheck not found")):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_timeout_expired(self, make_ctx):
        # shellcheck subprocess가 TimeoutExpired → 빈 이슈 목록 반환 (파이프라인 미중단)
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/script.sh")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="shellcheck", timeout=30)):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues == []

    def test_run_returns_empty_on_json_decode_error(self, make_ctx):
        # stdout이 유효하지 않은 JSON → JSONDecodeError → 빈 이슈 목록 반환
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        ctx = make_ctx(language="shell", tmp_path="/tmp/script.sh")
        with patch("subprocess.run", return_value=_mock_shellcheck_proc("{broken json")):
            issues = _ShellCheckAnalyzer().run(ctx)
        assert issues == []


# ──────────────────────────────────────────────────────────────────────────────
# TestShellCheckRegistration — 모듈 로드 시 REGISTRY 자동 등록 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestShellCheckRegistration:
    def test_module_import_registers_shellcheck_in_registry(self):
        # src.analyzer.io.tools.shellcheck 임포트 시 REGISTRY에 _ShellCheckAnalyzer가 자동 등록된다
        import importlib
        from src.analyzer.pure.registry import REGISTRY
        import src.analyzer.io.tools.shellcheck  # noqa: F401
        importlib.reload(src.analyzer.io.tools.shellcheck)
        names = [a.name for a in REGISTRY]
        assert "shellcheck" in names

    def test_double_import_does_not_duplicate_registry_entry(self):
        # 동일 모듈을 두 번 로드해도 REGISTRY에 "shellcheck"이 중복 등록되지 않아야 한다
        import importlib
        from src.analyzer.pure.registry import REGISTRY
        import src.analyzer.io.tools.shellcheck  # noqa: F401
        importlib.reload(src.analyzer.io.tools.shellcheck)
        importlib.reload(src.analyzer.io.tools.shellcheck)
        shellcheck_entries = [a for a in REGISTRY if a.name == "shellcheck"]
        assert len(shellcheck_entries) == 1

    def test_shellcheck_analyzer_satisfies_analyzer_protocol(self):
        # _ShellCheckAnalyzer 인스턴스가 Analyzer Protocol을 충족하는지 검증한다
        from src.analyzer.pure.registry import Analyzer
        from src.analyzer.io.tools.shellcheck import _ShellCheckAnalyzer
        assert isinstance(_ShellCheckAnalyzer(), Analyzer)
