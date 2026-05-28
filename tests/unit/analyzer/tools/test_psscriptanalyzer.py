"""psscriptanalyzer PowerShell 분석기 테스트.
psscriptanalyzer PowerShell analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "script.ps1", language: str = "powershell",
              content: str = "Write-Host 'Hello'") -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content=content, language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


def _mock_proc(stdout: str = "", returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


_PSSA_JSON = json.dumps([
    {
        "Message": "Avoid using Write-Host.",
        "Line": 1,
        "Severity": 2,
        "RuleName": "PSAvoidUsingWriteHost",
    },
    {
        "Message": "Script should use approved verbs.",
        "Line": 5,
        "Severity": 1,
        "RuleName": "PSUseApprovedVerbs",
    },
])


@pytest.fixture(autouse=True)
def _isolate_registry():
    """REGISTRY를 각 테스트마다 초기화한다.
    Reset REGISTRY for each test.
    """
    original = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


class TestPSScriptAnalyzer:
    def test_supports_powershell(self):
        # powershell 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for powershell language
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        assert _PSScriptAnalyzer().supports(_make_ctx("script.ps1", "powershell"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        assert not _PSScriptAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_is_enabled_when_installed(self):
        # pwsh 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when pwsh binary is present
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/bin/pwsh"):
            assert _PSScriptAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # pwsh 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when pwsh binary is absent
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _PSScriptAnalyzer().is_enabled(ctx) is False

    def test_parses_json_array(self):
        # PSScriptAnalyzer JSON 배열 출력을 파싱해 이슈를 반환해야 한다
        # Must parse PSScriptAnalyzer JSON array output and return issues
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_PSSA_JSON)):
            issues = _PSScriptAnalyzer().run(ctx)
        assert len(issues) == 2
        # Severity 2 → WARNING
        assert issues[0].severity == Severity.WARNING
        assert issues[0].line == 1
        assert issues[0].message == "Avoid using Write-Host."
        assert issues[0].category == Category.CODE_QUALITY
        # Severity 1 → ERROR
        assert issues[1].severity == Severity.ERROR
        assert issues[1].line == 5

    def test_severity_string_error(self):
        # Severity가 문자열 "Error"인 경우 Severity.ERROR를 반환해야 한다
        # Must return Severity.ERROR when Severity is the string "Error"
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        data = json.dumps([{"Message": "Bad verb.", "Line": 2, "Severity": "Error"}])
        with patch("subprocess.run", return_value=_mock_proc(data)):
            issues = _PSScriptAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pwsh", 30)):
            assert _PSScriptAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _PSScriptAnalyzer().run(ctx) == []

    def test_returns_empty_on_json_decode_error(self):
        # JSONDecodeError 시 빈 목록을 반환해야 한다
        # Must return empty list on JSONDecodeError
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("[not valid json]")):
            assert _PSScriptAnalyzer().run(ctx) == []

    def test_returns_empty_on_json_decode_error_explicit(self):
        """JSONDecodeError가 발생하면 빈 리스트를 반환한다.
        Returns empty list when JSONDecodeError occurs.
        """
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = json.JSONDecodeError("", "", 0)
            result = _PSScriptAnalyzer().run(ctx)
        assert result == []

    def test_returns_empty_on_non_array_output(self):
        # [로 시작하지 않는 출력은 빈 목록을 반환해야 한다
        # Output not starting with [ must return empty list
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("No results.", 0)):
            assert _PSScriptAnalyzer().run(ctx) == []

    def test_module_registers_psscriptanalyzer(self):
        # 모듈 임포트 시 REGISTRY에 psscriptanalyzer가 자동 등록된다
        # Module import must auto-register psscriptanalyzer in REGISTRY
        import importlib
        import src.analyzer.io.tools.psscriptanalyzer  # noqa: F401
        importlib.reload(src.analyzer.io.tools.psscriptanalyzer)
        names = [a.name for a in REGISTRY]
        assert "psscriptanalyzer" in names
