"""stylelint CSS/SCSS 정적 분석기 테스트.
stylelint CSS/SCSS static analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "style.css", language: str = "css", content: str = "body { color: red; }") -> AnalyzeContext:
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


# stylelint는 JSON 배열을 반환
# stylelint outputs a JSON array
_STYLELINT_JSON = json.dumps([
    {
        "source": "/tmp/style.css",
        "deprecations": [],
        "invalidOptionWarnings": [],
        "parseErrors": [],
        "warnings": [
            {
                "line": 2,
                "column": 3,
                "severity": "warning",
                "rule": "color-named",
                "text": "Unexpected named color \"red\" (color-named)",
            },
            {
                "line": 5,
                "column": 1,
                "severity": "error",
                "rule": "selector-max-id",
                "text": "Expected \"#main\" to have no more than 0 ID selectors (selector-max-id)",
            },
        ]
    }
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


class TestStylelintAnalyzer:
    def test_supports_css(self):
        # css 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for css language
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        assert _StylelintAnalyzer().supports(_make_ctx("style.css", "css"))

    def test_supports_scss(self):
        # scss 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for scss language
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        assert _StylelintAnalyzer().supports(_make_ctx("style.scss", "scss"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        assert not _StylelintAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_does_not_support_javascript(self):
        # javascript 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for javascript language
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        assert not _StylelintAnalyzer().supports(_make_ctx("app.js", "javascript"))

    def test_is_enabled_when_installed(self):
        # stylelint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when stylelint binary is present
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/local/bin/stylelint"):
            assert _StylelintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # stylelint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when stylelint binary is absent
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _StylelintAnalyzer().is_enabled(ctx) is False

    def test_parses_warnings(self):
        # stylelint JSON 배열의 warnings를 파싱해 이슈를 반환해야 한다
        # Must parse warnings from stylelint JSON array and return issues
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_STYLELINT_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/stylelint"):
                issues = _StylelintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 2
        assert issues[1].line == 5

    def test_severity_mapping(self):
        # severity 필드가 올바르게 매핑되어야 한다 (warning → WARNING, error → ERROR)
        # severity field must be mapped correctly (warning → WARNING, error → ERROR)
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_STYLELINT_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/stylelint"):
                issues = _StylelintAnalyzer().run(ctx)
        assert issues[0].severity == Severity.WARNING
        assert issues[1].severity == Severity.ERROR

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("stylelint", 30)):
            assert _StylelintAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 발생 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _StylelintAnalyzer().run(ctx) == []

    def test_returns_empty_on_non_array_output(self):
        # JSON 배열이 아닌 출력('[' 미시작)은 빈 목록을 반환해야 한다
        # Non-JSON-array output (not starting with '[') must return empty list
        from src.analyzer.io.tools.stylelint import _StylelintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("No files found")):
            assert _StylelintAnalyzer().run(ctx) == []

    def test_module_registers_stylelint(self):
        # 모듈 임포트 시 REGISTRY에 stylelint가 자동 등록된다
        # Module import must auto-register stylelint in REGISTRY
        import importlib
        import src.analyzer.io.tools.stylelint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.stylelint)
        names = [a.name for a in REGISTRY]
        assert "stylelint" in names
