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


# ──────────────────────────────────────────────────────────────────────────────
# 스폰 축 fail-closed (#1557 W3)
#
# 🔴 `except OSError` 는 두 가지를 한 갈래로 보냈다: 「바이너리가 없다」(조달 축)와
#    「which() 를 통과했는데 실행이 실패했다」(미분석). 후자는 깨진 shebang·권한·TOCTOU 이고
#    분석이 **안 된** 것이므로 `[]` 로 돌려주면 그 침묵이 «이슈 0건 · 완전» 이 된다.
#    `FileNotFoundError` 로 좁히면 앞은 그대로 `[]`, 뒤는 올라가 `static.py` 가 incomplete 로 승격한다.
# A spawn failure after which() succeeded is unanalyzed, not "binary absent".
# ──────────────────────────────────────────────────────────────────────────────


class TestTscSpawnAxisFailClosed:
    def test_file_not_found_still_returns_empty(self):
        """대조군 — 바이너리 부재는 조달 축이다."""
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        ctx = _make_ctx("typescript", "app.ts")
        with patch("subprocess.run", side_effect=FileNotFoundError("tsc not found")):
            with patch("shutil.which", return_value="/usr/bin/tsc"):
                assert _TscAnalyzer().run(ctx) == []

    @pytest.mark.parametrize("exc", [
        PermissionError("permission denied"),
        OSError(8, "Exec format error"),
    ], ids=["permission", "enoexec"])
    def test_spawn_failure_is_not_a_clean_run(self, exc):
        """🔴 which() 통과 후의 실행 실패는 미분석 — 올라가야 한다."""
        from src.analyzer.io.tools.tsc import _TscAnalyzer
        ctx = _make_ctx("typescript", "app.ts")
        with patch("subprocess.run", side_effect=exc):
            with patch("shutil.which", return_value="/usr/bin/tsc"):
                with pytest.raises(OSError):
                    _TscAnalyzer().run(ctx)
