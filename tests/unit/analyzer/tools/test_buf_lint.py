"""buf_lint Protobuf 분석기 테스트.
buf_lint Protobuf analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "test.proto", language: str = "protobuf",
              content: str = 'syntax = "proto3";') -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content=content, language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


def _mock_proc(stdout: str = "", returncode: int = 1) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


@pytest.fixture(autouse=True)
def _isolate_registry():
    """REGISTRY를 각 테스트마다 초기화한다.
    Reset REGISTRY for each test.
    """
    original = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


class TestBufLintAnalyzer:
    def test_supports_protobuf(self):
        # protobuf 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for protobuf language
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        assert _BufLintAnalyzer().supports(_make_ctx("test.proto", "protobuf"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        assert not _BufLintAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_is_enabled_when_installed(self):
        # buf 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when buf binary is present
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value="/usr/local/bin/buf"):
            assert _BufLintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # buf 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when buf binary is absent
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _BufLintAnalyzer().is_enabled(ctx) is False

    def test_parses_jsonl_output(self):
        # buf JSONL 출력의 각 줄을 파싱해 이슈를 반환해야 한다
        # Must parse each JSONL line from buf output and return issues
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        ctx = _make_ctx()
        line1 = json.dumps({"start_line": 5, "message": "Field name should be lower_snake_case"})
        line2 = json.dumps({"start_line": 12, "message": "Use proto3 syntax"})
        stdout = f"{line1}\n{line2}\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BufLintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 5
        assert issues[0].message == "Field name should be lower_snake_case"
        assert issues[1].line == 12
        assert issues[0].category == Category.CODE_QUALITY
        assert issues[0].severity == Severity.WARNING

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("buf", 30)):
            assert _BufLintAnalyzer().run(ctx) == []

    def test_returns_empty_on_oserror(self):
        # OSError 시 빈 목록을 반환해야 한다
        # Must return empty list on OSError
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=OSError("not found")):
            assert _BufLintAnalyzer().run(ctx) == []

    def test_skips_invalid_jsonl_lines(self):
        # JSONL 중 유효하지 않은 줄은 조용히 무시해야 한다
        # Invalid JSONL lines must be silently skipped
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        ctx = _make_ctx()
        line1 = json.dumps({"start_line": 3, "message": "Valid issue"})
        stdout = f"{line1}\nnot-json-at-all\n\n"
        with patch("subprocess.run", return_value=_mock_proc(stdout)):
            issues = _BufLintAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].line == 3

    def test_returns_empty_on_empty_output(self):
        # 빈 stdout은 빈 이슈 목록을 반환해야 한다
        # Empty stdout must return an empty issue list
        from src.analyzer.io.tools.buf_lint import _BufLintAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc("", 0)):
            assert _BufLintAnalyzer().run(ctx) == []

    def test_module_registers_buf_lint(self):
        # 모듈 임포트 시 REGISTRY에 buf_lint가 자동 등록된다
        # Module import must auto-register buf_lint in REGISTRY
        import importlib
        import src.analyzer.io.tools.buf_lint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.buf_lint)
        names = [a.name for a in REGISTRY]
        assert "buf_lint" in names
