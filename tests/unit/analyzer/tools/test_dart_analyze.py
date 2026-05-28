"""dart_analyze Dart 분석기 테스트.
dart_analyze Dart analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "main.dart", language: str = "dart",
              content: str = "void main() {}") -> AnalyzeContext:
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


_DART_JSON = json.dumps({
    "version": 1,
    "diagnostics": [
        {
            "severity": "ERROR",
            "problemMessage": "Undefined name 'foo'.",
            "location": {
                "file": "/tmp/main.dart",
                "range": {
                    "start": {"offset": 10, "line": 3, "column": 5},
                    "end": {"offset": 13, "line": 3, "column": 8},
                }
            }
        },
        {
            "severity": "WARNING",
            "problemMessage": "Unused import.",
            "location": {
                "file": "/tmp/main.dart",
                "range": {
                    "start": {"offset": 0, "line": 1, "column": 1},
                    "end": {"offset": 20, "line": 1, "column": 21},
                }
            }
        },
    ]
})


@pytest.fixture(autouse=True)
def _isolate_registry():
    """REGISTRY를 각 테스트마다 초기화한다.
    Reset REGISTRY for each test.
    """
    original = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


class TestDartAnalyzer:
    def test_supports_dart(self):
        # dart 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for dart language
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        assert _DartAnalyzer().supports(_make_ctx("main.dart", "dart"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        assert not _DartAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_is_enabled_when_installed(self):
        # dart 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when dart binary is present
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/bin/dart"):
            assert _DartAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # dart 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when dart binary is absent
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _DartAnalyzer().is_enabled(ctx) is False

    def test_parses_diagnostics(self):
        # dart JSON 출력의 diagnostics를 파싱해 이슈를 반환해야 한다
        # Must parse diagnostics from dart JSON output and return issues
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_DART_JSON)):
            issues = _DartAnalyzer().run(ctx)
        assert len(issues) == 2
        # 첫 번째: ERROR → Severity.ERROR
        # First: ERROR → Severity.ERROR
        assert issues[0].severity == Severity.ERROR
        assert issues[0].line == 3
        assert issues[0].message == "Undefined name 'foo'."
        assert issues[0].category == Category.CODE_QUALITY
        # 두 번째: WARNING → Severity.WARNING
        # Second: WARNING → Severity.WARNING
        assert issues[1].severity == Severity.WARNING
        assert issues[1].line == 1

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("dart", 30)):
            assert _DartAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _DartAnalyzer().run(ctx) == []

    def test_returns_empty_on_json_decode_error(self):
        # JSONDecodeError 시 빈 목록을 반환해야 한다
        # Must return empty list on JSONDecodeError
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        # { 로 시작하지만 JSON이 아닌 출력
        # Starts with { but invalid JSON
        with patch("subprocess.run", return_value=_mock_proc("{invalid json}")):
            assert _DartAnalyzer().run(ctx) == []

    def test_returns_empty_on_json_decode_error_explicit(self):
        """JSONDecodeError가 발생하면 빈 리스트를 반환한다.
        Returns empty list when JSONDecodeError occurs.
        """
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = json.JSONDecodeError("", "", 0)
            result = _DartAnalyzer().run(ctx)
        assert result == []

    def test_returns_empty_on_non_json_output(self):
        # {로 시작하지 않는 출력은 빈 목록을 반환해야 한다
        # Output not starting with { must return empty list
        from src.analyzer.io.tools.dart_analyze import _DartAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("No issues found\n", 0)):
            assert _DartAnalyzer().run(ctx) == []

    def test_module_registers_dart_analyze(self):
        # 모듈 임포트 시 REGISTRY에 dart_analyze가 자동 등록된다
        # Module import must auto-register dart_analyze in REGISTRY
        import importlib
        import src.analyzer.io.tools.dart_analyze  # noqa: F401
        importlib.reload(src.analyzer.io.tools.dart_analyze)
        names = [a.name for a in REGISTRY]
        assert "dart_analyze" in names
