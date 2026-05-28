"""htmlhint HTML 정적 분석기 테스트.
htmlhint HTML static analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "index.html", language: str = "html", content: str = "<html><body></body></html>") -> AnalyzeContext:
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


# htmlhint는 JSON 배열을 반환
# htmlhint outputs a JSON array
_HTMLHINT_JSON = json.dumps([
    {
        "file": "/tmp/index.html",
        "messages": [
            {
                "rule": {"id": "doctype-first", "description": "Doctype must be declared first."},
                "line": 1,
                "col": 1,
                "message": "Doctype must be declared first.",
                "type": "error",
            },
            {
                "rule": {"id": "attr-lowercase", "description": "Attribute name must be lowercase."},
                "line": 3,
                "col": 5,
                "message": "Attribute name ( HREF ) must be lowercase.",
                "type": "warning",
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


class TestHtmlhintAnalyzer:
    def test_supports_html(self):
        # html 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for html language
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        assert _HtmlhintAnalyzer().supports(_make_ctx("index.html", "html"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        assert not _HtmlhintAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_does_not_support_css(self):
        # css 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for css language
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        assert not _HtmlhintAnalyzer().supports(_make_ctx("style.css", "css"))

    def test_is_enabled_when_installed(self):
        # htmlhint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when htmlhint binary is present
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/local/bin/htmlhint"):
            assert _HtmlhintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # htmlhint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when htmlhint binary is absent
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _HtmlhintAnalyzer().is_enabled(ctx) is False

    def test_parses_messages(self):
        # htmlhint JSON 배열의 messages를 파싱해 이슈를 반환해야 한다
        # Must parse messages from htmlhint JSON array and return issues
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_HTMLHINT_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/htmlhint"):
                issues = _HtmlhintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 1
        assert issues[1].line == 3

    def test_severity_mapping(self):
        # type 필드가 올바르게 severity로 매핑되어야 한다 (error → ERROR, warning → WARNING)
        # type field must be mapped correctly to severity (error → ERROR, warning → WARNING)
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_HTMLHINT_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/htmlhint"):
                issues = _HtmlhintAnalyzer().run(ctx)
        assert issues[0].severity == Severity.ERROR
        assert issues[1].severity == Severity.WARNING

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("htmlhint", 30)):
            assert _HtmlhintAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 발생 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _HtmlhintAnalyzer().run(ctx) == []

    def test_returns_empty_on_non_array_output(self):
        # JSON 배열이 아닌 출력('[' 미시작)은 빈 목록을 반환해야 한다
        # Non-JSON-array output (not starting with '[') must return empty list
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("htmlhint: command not found")):
            assert _HtmlhintAnalyzer().run(ctx) == []

    def test_returns_empty_on_json_decode_error(self):
        # JSONDecodeError가 발생하면 빈 리스트를 반환한다
        # Returns empty list when JSONDecodeError occurs
        from src.analyzer.io.tools.htmlhint import _HtmlhintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=json.JSONDecodeError("", "", 0)):
            assert _HtmlhintAnalyzer().run(ctx) == []

    def test_module_registers_htmlhint(self):
        # 모듈 임포트 시 REGISTRY에 htmlhint가 자동 등록된다
        # Module import must auto-register htmlhint in REGISTRY
        import importlib
        import src.analyzer.io.tools.htmlhint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.htmlhint)
        names = [a.name for a in REGISTRY]
        assert "htmlhint" in names
