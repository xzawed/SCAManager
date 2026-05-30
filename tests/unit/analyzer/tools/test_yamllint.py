"""yamllint YAML 분석기 테스트.
yamllint YAML analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, REGISTRY


def _make_ctx(language: str, filename: str) -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content="", language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


_YAMLLINT_JSON = json.dumps([
    {"line": 3, "column": 1, "level": "error",
     "message": "wrong indentation: expected 2 but found 4", "rule": "indentation"},
    {"line": 10, "column": 5, "level": "warning",
     "message": "too many spaces before colon", "rule": "colons"},
])


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


class TestYamllintAnalyzer:
    def test_supports_yaml(self):
        # yaml 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for yaml language
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        assert _YamllintAnalyzer().supports(_make_ctx("yaml", "config.yaml"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        assert not _YamllintAnalyzer().supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_installed(self):
        # yamllint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when yamllint binary is present
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("shutil.which", return_value="/usr/bin/yamllint"):
            assert _YamllintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # yamllint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when yamllint binary is absent
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("shutil.which", return_value=None):
            assert _YamllintAnalyzer().is_enabled(ctx) is False

    def test_parses_json_output(self):
        # yamllint JSON 출력을 파싱해 2개의 이슈를 반환해야 한다
        # Must parse yamllint JSON output and return 2 issues
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("subprocess.run") as mock_run:
            with patch("shutil.which", return_value="/usr/bin/yamllint"):
                mock_run.return_value = _mock_proc(_YAMLLINT_JSON)
                issues = _YamllintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 3
        assert issues[0].severity == Severity.ERROR
        assert issues[1].line == 10
        assert issues[1].severity == Severity.WARNING

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("yamllint", 30)):
            with patch("shutil.which", return_value="/usr/bin/yamllint"):
                assert _YamllintAnalyzer().run(ctx) == []

    def test_returns_empty_on_empty_output(self):
        # 빈 stdout은 빈 이슈 목록을 반환해야 한다
        # Empty stdout must return an empty issue list
        from src.analyzer.io.tools.yamllint import _YamllintAnalyzer
        ctx = _make_ctx("yaml", "config.yaml")
        with patch("subprocess.run", return_value=_mock_proc("", 0)):
            issues = _YamllintAnalyzer().run(ctx)
        assert issues == []

    def test_module_registers_yamllint(self):
        # 모듈 임포트 시 REGISTRY에 yamllint가 자동 등록된다
        # Module import must auto-register yamllint in REGISTRY
        import importlib
        import src.analyzer.io.tools.yamllint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.yamllint)
        names = [a.name for a in REGISTRY]
        assert "yamllint" in names
