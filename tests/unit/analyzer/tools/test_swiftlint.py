"""swiftlint Swift 정적 분석기 테스트.
swiftlint Swift static analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "main.swift", language: str = "swift", content: str = "import Foundation") -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content=content, language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


def _mock_proc(stdout: str = "", returncode: int = 0):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


# swiftlint는 JSON 배열을 반환
# swiftlint outputs a JSON array
_SWIFTLINT_JSON = json.dumps([
    {
        "file": "/tmp/main.swift",
        "line": 3,
        "reason": "Trailing whitespace",
        "severity": "warning",
        "type": "Trailing Whitespace",
    },
    {
        "file": "/tmp/main.swift",
        "line": 7,
        "reason": "Force cast should be avoided",
        "severity": "error",
        "type": "Force Cast",
    },
])


@pytest.fixture(autouse=True)
def _isolate_registry():
    """테스트 간 REGISTRY 오염 방지.
    Prevent REGISTRY pollution between tests.
    """
    before = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(before)


class TestSwiftlintAnalyzer:
    def test_supports_swift(self):
        # swift 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for swift language
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        assert _SwiftlintAnalyzer().supports(_make_ctx("main.swift", "swift"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        assert not _SwiftlintAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_does_not_support_kotlin(self):
        # kotlin 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for kotlin language
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        assert not _SwiftlintAnalyzer().supports(_make_ctx("App.kt", "kotlin"))

    def test_is_enabled_when_installed(self):
        # swiftlint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when swiftlint binary is present
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/local/bin/swiftlint"):
            assert _SwiftlintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # swiftlint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when swiftlint binary is absent
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _SwiftlintAnalyzer().is_enabled(ctx) is False

    def test_parses_issues(self):
        # swiftlint JSON 배열을 파싱해 이슈를 반환해야 한다
        # Must parse swiftlint JSON array and return issues
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_SWIFTLINT_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/swiftlint"):
                issues = _SwiftlintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 3
        assert issues[1].line == 7

    def test_severity_mapping(self):
        # severity 필드가 올바르게 매핑되어야 한다 (warning → WARNING, error → ERROR)
        # severity field must be mapped correctly (warning → WARNING, error → ERROR)
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_SWIFTLINT_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/swiftlint"):
                issues = _SwiftlintAnalyzer().run(ctx)
        assert issues[0].severity == Severity.WARNING
        assert issues[1].severity == Severity.ERROR

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("swiftlint", 30)):
            assert _SwiftlintAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 발생 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _SwiftlintAnalyzer().run(ctx) == []

    def test_returns_empty_on_non_array_output(self):
        # JSON 배열이 아닌 출력('[' 미시작)은 빈 목록을 반환해야 한다
        # Non-JSON-array output (not starting with '[') must return empty list
        from src.analyzer.io.tools.swiftlint import _SwiftlintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("No lintable files found")):
            assert _SwiftlintAnalyzer().run(ctx) == []

    def test_module_registers_swiftlint(self):
        # 모듈 임포트 시 REGISTRY에 swiftlint가 자동 등록된다
        # Module import must auto-register swiftlint in REGISTRY
        import importlib
        import src.analyzer.io.tools.swiftlint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.swiftlint)
        names = [a.name for a in REGISTRY]
        assert "swiftlint" in names
