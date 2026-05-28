"""phpstan PHP 정적 분석기 테스트.
phpstan PHP static analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "test.php", language: str = "php", content: str = "<?php echo 1;") -> AnalyzeContext:
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


# phpstan은 JSON 객체(배열 아님)를 반환
# phpstan outputs a JSON object (not an array)
_PHPSTAN_JSON = json.dumps({
    "totals": {"errors": 2, "file_errors": 2},
    "files": {
        "/tmp/test.php": {
            "errors": 2,
            "messages": [
                {"message": "Undefined variable: $x", "line": 5, "ignorable": True},
                {"message": "Parameter #1 ...", "line": 10, "ignorable": True},
            ]
        }
    },
    "errors": []
})


@pytest.fixture(autouse=True)
def _isolate_registry():
    """테스트 간 REGISTRY 오염 방지.
    Prevent REGISTRY pollution between tests.
    """
    before = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(before)


class TestPhpstanAnalyzer:
    def test_supports_php(self):
        # php 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for php language
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        assert _PhpstanAnalyzer().supports(_make_ctx("test.php", "php"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        assert not _PhpstanAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_does_not_support_javascript(self):
        # javascript 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for javascript language
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        assert not _PhpstanAnalyzer().supports(_make_ctx("app.js", "javascript"))

    def test_is_enabled_when_installed(self):
        # phpstan 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when phpstan binary is present
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/local/bin/phpstan"):
            assert _PhpstanAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # phpstan 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when phpstan binary is absent
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _PhpstanAnalyzer().is_enabled(ctx) is False

    def test_parses_errors(self):
        # phpstan JSON 출력의 files.messages를 파싱해 이슈를 반환해야 한다
        # Must parse files.messages from phpstan JSON output and return issues
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_PHPSTAN_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/phpstan"):
                issues = _PhpstanAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 5
        assert issues[1].line == 10
        assert issues[0].severity == Severity.ERROR

    def test_all_issues_are_error_severity(self):
        # phpstan의 모든 이슈는 ERROR 심각도를 가져야 한다
        # All phpstan issues must have ERROR severity
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_PHPSTAN_JSON)):
            with patch("shutil.which", return_value="/usr/local/bin/phpstan"):
                issues = _PhpstanAnalyzer().run(ctx)
        assert all(i.severity == Severity.ERROR for i in issues)

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("phpstan", 30)):
            assert _PhpstanAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 발생 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _PhpstanAnalyzer().run(ctx) == []

    def test_returns_empty_on_non_json_output(self):
        # JSON 객체가 아닌 출력('{' 미시작)은 빈 목록을 반환해야 한다
        # Non-JSON-object output (not starting with '{') must return empty list
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("Error: some text")):
            assert _PhpstanAnalyzer().run(ctx) == []

    def test_returns_empty_on_json_decode_error(self):
        # JSONDecodeError가 발생하면 빈 리스트를 반환한다
        # Returns empty list when JSONDecodeError occurs
        from src.analyzer.io.tools.phpstan import _PhpstanAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=json.JSONDecodeError("", "", 0)):
            assert _PhpstanAnalyzer().run(ctx) == []

    def test_module_registers_phpstan(self):
        # 모듈 임포트 시 REGISTRY에 phpstan이 자동 등록된다
        # Module import must auto-register phpstan in REGISTRY
        import importlib
        import src.analyzer.io.tools.phpstan  # noqa: F401
        importlib.reload(src.analyzer.io.tools.phpstan)
        names = [a.name for a in REGISTRY]
        assert "phpstan" in names
