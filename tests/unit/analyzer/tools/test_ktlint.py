"""ktlint Kotlin 분석기 테스트.
ktlint Kotlin analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, REGISTRY


def _make_ctx(language: str, filename: str) -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content="", language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


_KTLINT_JSON = json.dumps([{
    "file": "/tmp/Main.kt",
    "errors": [
        {"line": 3, "column": 1, "message": "Unexpected indentation", "rule": "indent"},
        {"line": 8, "column": 10, "message": "Missing newline before '{'", "rule": "brace-style"},
    ]
}])


def _mock_proc(stdout: str = "", returncode: int = 1):
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


@pytest.fixture(autouse=True)
def _isolate_registry():
    """테스트 간 REGISTRY 오염 방지."""
    before = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(before)


class TestKtlintAnalyzer:
    def test_supports_kotlin(self):
        # kotlin 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for kotlin language
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        assert _KtlintAnalyzer().supports(_make_ctx("kotlin", "Main.kt"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        assert not _KtlintAnalyzer().supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_installed(self):
        # ktlint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when ktlint binary is present
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        ctx = _make_ctx("kotlin", "Main.kt")
        with patch("shutil.which", return_value="/usr/bin/ktlint"):
            assert _KtlintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # ktlint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when ktlint binary is absent
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        ctx = _make_ctx("kotlin", "Main.kt")
        with patch("shutil.which", return_value=None):
            assert _KtlintAnalyzer().is_enabled(ctx) is False

    def test_parses_errors(self):
        # ktlint JSON 출력의 errors를 파싱해 이슈를 반환해야 한다
        # Must parse errors from ktlint JSON output and return issues
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        ctx = _make_ctx("kotlin", "Main.kt")
        with patch("subprocess.run") as mock_run:
            with patch("shutil.which", return_value="/usr/bin/ktlint"):
                mock_run.return_value = _mock_proc(_KTLINT_JSON)
                issues = _KtlintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 3
        assert issues[1].line == 8

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        ctx = _make_ctx("kotlin", "Main.kt")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ktlint", 30)):
            with patch("shutil.which", return_value="/usr/bin/ktlint"):
                assert _KtlintAnalyzer().run(ctx) == []

    def test_returns_empty_on_empty_output(self):
        # 빈 stdout은 빈 이슈 목록을 반환해야 한다
        # Empty stdout must return an empty issue list
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        ctx = _make_ctx("kotlin", "Main.kt")
        with patch("subprocess.run", return_value=_mock_proc("", 0)):
            issues = _KtlintAnalyzer().run(ctx)
        assert issues == []

    def test_module_registers_ktlint(self):
        # 모듈 임포트 시 REGISTRY에 ktlint가 자동 등록된다
        # Module import must auto-register ktlint in REGISTRY
        import importlib
        import src.analyzer.io.tools.ktlint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.ktlint)
        names = [a.name for a in REGISTRY]
        assert "ktlint" in names
