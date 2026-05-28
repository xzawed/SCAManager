"""dotnet_format C# 분석기 테스트.
dotnet_format C# analyzer tests.
"""
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "Program.cs", language: str = "csharp",
              content: str = "class Program { }") -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content=content, language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


def _mock_proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


# dotnet format 진단 출력 샘플
# Sample dotnet format diagnostic output
_DOTNET_STDERR = (
    "/tmp/Program.cs(5,10): warning IDE0055: Fix formatting\n"
    "/tmp/Program.cs(12,1): error CS0001: Compilation failed\n"
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """REGISTRY를 각 테스트마다 초기화한다.
    Reset REGISTRY for each test.
    """
    original = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


class TestDotnetFormatAnalyzer:
    def test_supports_csharp(self):
        # csharp 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for csharp language
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        assert _DotnetFormatAnalyzer().supports(_make_ctx("Program.cs", "csharp"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        assert not _DotnetFormatAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_is_enabled_when_installed(self):
        # dotnet 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when dotnet binary is present
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/bin/dotnet"):
            assert _DotnetFormatAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # dotnet 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when dotnet binary is absent
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _DotnetFormatAnalyzer().is_enabled(ctx) is False

    def test_parses_stderr_diagnostics(self):
        # stderr의 진단 출력을 파싱해 이슈를 반환해야 한다
        # Must parse diagnostics from stderr and return issues
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run",
                   return_value=_mock_proc(stderr=_DOTNET_STDERR, returncode=1)):
            issues = _DotnetFormatAnalyzer().run(ctx)
        assert len(issues) == 2
        # 첫 번째: warning → WARNING
        # First: warning → WARNING
        assert issues[0].severity == Severity.WARNING
        assert issues[0].line == 5
        assert issues[0].message == "Fix formatting"
        assert issues[0].category == Category.CODE_QUALITY
        # 두 번째: error → ERROR
        # Second: error → ERROR
        assert issues[1].severity == Severity.ERROR
        assert issues[1].line == 12

    def test_parses_stdout_when_no_stderr(self):
        # stderr가 없을 때 stdout에서 진단을 파싱해야 한다
        # Must parse diagnostics from stdout when stderr is empty
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        ctx = _make_ctx()
        stdout_diag = "/tmp/Program.cs(3,5): warning IDE0001: Simplify name\n"
        with patch("subprocess.run",
                   return_value=_mock_proc(stdout=stdout_diag, returncode=1)):
            issues = _DotnetFormatAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].line == 3
        assert issues[0].severity == Severity.WARNING

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("dotnet", 30)):
            assert _DotnetFormatAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _DotnetFormatAnalyzer().run(ctx) == []

    def test_returns_empty_when_no_diagnostics(self):
        # 진단이 없는 출력은 빈 목록을 반환해야 한다
        # Output with no diagnostics must return empty list
        from src.analyzer.io.tools.dotnet_format import _DotnetFormatAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run",
                   return_value=_mock_proc(stdout="", stderr="", returncode=0)):
            assert _DotnetFormatAnalyzer().run(ctx) == []

    def test_module_registers_dotnet_format(self):
        # 모듈 임포트 시 REGISTRY에 dotnet_format이 자동 등록된다
        # Module import must auto-register dotnet_format in REGISTRY
        import importlib
        import src.analyzer.io.tools.dotnet_format  # noqa: F401
        importlib.reload(src.analyzer.io.tools.dotnet_format)
        names = [a.name for a in REGISTRY]
        assert "dotnet_format" in names
