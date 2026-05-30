"""tsc TypeScript 타입체크 분석기 테스트."""
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, REGISTRY


def _make_ctx(language: str, filename: str) -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content="", language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


def _mock_tsc_proc(stdout: str = "", stderr: str = "", returncode: int = 1):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = stderr
    m.returncode = returncode
    return m


_TSC_ERROR_OUTPUT = (
    "/tmp/app.ts(10,5): error TS2322: "
    "Type 'string' is not assignable to type 'number'.\n"
    "/tmp/app.ts(20,1): warning TS80001: "
    "The 'import.meta' meta-property is only allowed.\n"
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    """레지스트리 오염 방지 — 테스트 전후로 REGISTRY 상태 복원.
    Prevent registry pollution — restore REGISTRY state before and after each test.
    """
    before = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(before)


class TestTscAnalyzer:
    def test_supports_typescript(self):
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        a = _TscAnalyzer()
        assert a.supports(_make_ctx("typescript", "app.ts"))

    def test_does_not_support_python(self):
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        a = _TscAnalyzer()
        assert not a.supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_tsc_installed(self):
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        with patch("shutil.which", return_value="/usr/bin/tsc"):
            assert _TscAnalyzer().is_enabled(_make_ctx("typescript", "app.ts"))

    def test_is_enabled_false_when_missing(self):
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        with patch("shutil.which", return_value=None):
            assert not _TscAnalyzer().is_enabled(_make_ctx("typescript", "app.ts"))

    def test_parses_error_output(self):
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        ctx = _make_ctx("typescript", "app.ts")
        with patch("subprocess.run") as mock_run:
            with patch("shutil.which", return_value="/usr/bin/tsc"):
                mock_run.return_value = _mock_tsc_proc(stderr=_TSC_ERROR_OUTPUT, returncode=2)
                issues = _TscAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 10
        assert issues[0].severity == Severity.ERROR
        assert issues[1].line == 20
        assert issues[1].severity == Severity.WARNING

    def test_returns_empty_on_timeout(self):
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        ctx = _make_ctx("typescript", "app.ts")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("tsc", 30)):
            with patch("shutil.which", return_value="/usr/bin/tsc"):
                issues = _TscAnalyzer().run(ctx)
        assert issues == []

    def test_tsx_is_supported(self):
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        a = _TscAnalyzer()
        # TypeScript 언어 감지기는 .tsx도 "typescript"로 감지함
        # The language detector classifies .tsx as "typescript"
        assert a.supports(_make_ctx("typescript", "component.tsx"))
