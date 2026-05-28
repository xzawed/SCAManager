"""hadolint Dockerfile 분석기 테스트.
hadolint Dockerfile analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(language: str, filename: str) -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content="", language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


_HADOLINT_JSON = json.dumps([
    {"line": 5, "code": "DL3009",
     "message": "Delete the apt-get lists after installing something",
     "column": 1, "file": "/tmp/Dockerfile", "level": "warning"},
    {"line": 10, "code": "DL3008",
     "message": "Pin versions in apt get install",
     "column": 1, "file": "/tmp/Dockerfile", "level": "error"},
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


class TestHadolintAnalyzer:
    def test_supports_dockerfile(self):
        # dockerfile 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for dockerfile language
        from src.analyzer.io.tools.hadolint import _HadolintAnalyzer
        a = _HadolintAnalyzer()
        assert a.supports(_make_ctx("dockerfile", "Dockerfile"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.hadolint import _HadolintAnalyzer
        assert not _HadolintAnalyzer().supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_installed(self):
        # hadolint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when hadolint binary is present
        from src.analyzer.io.tools.hadolint import _HadolintAnalyzer
        ctx = _make_ctx("dockerfile", "Dockerfile")
        with patch("shutil.which", return_value="/usr/bin/hadolint"):
            assert _HadolintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # hadolint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when hadolint binary is absent
        from src.analyzer.io.tools.hadolint import _HadolintAnalyzer
        ctx = _make_ctx("dockerfile", "Dockerfile")
        with patch("shutil.which", return_value=None):
            assert _HadolintAnalyzer().is_enabled(ctx) is False

    def test_parses_json_output(self):
        # hadolint JSON 출력을 파싱해 2개의 이슈를 반환해야 한다
        # Must parse hadolint JSON output and return 2 issues
        from src.analyzer.io.tools.hadolint import _HadolintAnalyzer
        ctx = _make_ctx("dockerfile", "Dockerfile")
        with patch("subprocess.run") as mock_run:
            with patch("shutil.which", return_value="/usr/bin/hadolint"):
                mock_run.return_value = _mock_proc(_HADOLINT_JSON)
                issues = _HadolintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 5
        assert issues[0].severity == Severity.WARNING
        assert issues[1].line == 10
        assert issues[1].severity == Severity.ERROR

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.hadolint import _HadolintAnalyzer
        ctx = _make_ctx("dockerfile", "Dockerfile")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("hadolint", 30)):
            with patch("shutil.which", return_value="/usr/bin/hadolint"):
                assert _HadolintAnalyzer().run(ctx) == []

    def test_returns_empty_when_not_installed(self):
        # hadolint 바이너리가 없으면 is_enabled()가 False를 반환해 분석이 스킵된다
        # is_enabled() returning False ensures the analyzer is skipped
        from src.analyzer.io.tools.hadolint import _HadolintAnalyzer
        ctx = _make_ctx("dockerfile", "Dockerfile")
        with patch("shutil.which", return_value=None):
            assert not _HadolintAnalyzer().is_enabled(ctx)

    def test_module_registers_hadolint(self):
        # 모듈 임포트 시 REGISTRY에 hadolint가 자동 등록된다
        # Module import must auto-register hadolint in REGISTRY
        import importlib
        import src.analyzer.io.tools.hadolint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.hadolint)
        names = [a.name for a in REGISTRY]
        assert "hadolint" in names
