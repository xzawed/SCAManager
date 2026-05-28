"""clippy Rust 분석기 테스트.
clippy Rust analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(language: str, filename: str, content: str = "fn main() {}") -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content=content, language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


# cargo clippy --message-format=json 출력 — compiler-message 행만 처리
# cargo clippy --message-format=json output — only compiler-message lines are processed
_CLIPPY_JSONL = "\n".join([
    json.dumps({"reason": "compiler-message", "message": {
        "message": "unused variable: `x`",
        "level": "warning",
        "spans": [{"line_start": 3}],
    }}),
    json.dumps({"reason": "compiler-message", "message": {
        "message": "this expression can be simplified",
        "level": "error",
        "spans": [{"line_start": 7}],
    }}),
    json.dumps({"reason": "build-script-executed"}),  # 무시해야 할 행 / must be ignored
])


def _mock_proc(stdout: str = "", returncode: int = 0):
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


class TestClippyAnalyzer:
    def test_supports_rust(self):
        # rust 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for rust language
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        assert _ClippyAnalyzer().supports(_make_ctx("rust", "main.rs"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        assert not _ClippyAnalyzer().supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_cargo_installed(self):
        # cargo 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when cargo binary is present
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        ctx = _make_ctx("rust", "main.rs")
        with patch("shutil.which", return_value="/usr/bin/cargo"):
            assert _ClippyAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_cargo_missing(self):
        # cargo 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when cargo binary is absent
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        ctx = _make_ctx("rust", "main.rs")
        with patch("shutil.which", return_value=None):
            assert _ClippyAnalyzer().is_enabled(ctx) is False

    def test_parses_compiler_messages_only(self):
        # compiler-message만 파싱하고 다른 reason 행은 무시해야 한다
        # Must parse only compiler-message lines and ignore all other reason values
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        ctx = _make_ctx("rust", "main.rs")
        with patch("subprocess.run") as mock_run:
            with patch("shutil.which", return_value="/usr/bin/cargo"):
                with patch("tempfile.mkdtemp", return_value="/tmp/clippy_test"):
                    with patch("os.makedirs"):
                        with patch("builtins.open", MagicMock()):
                            with patch("shutil.rmtree"):
                                mock_run.return_value = _mock_proc(_CLIPPY_JSONL, 0)
                                issues = _ClippyAnalyzer().run(ctx)
        # build-script-executed 행은 무시 — compiler-message 2개만 파싱
        # build-script-executed lines ignored — only 2 compiler-message entries
        assert len(issues) == 2
        assert issues[0].line == 3
        assert issues[0].severity == Severity.WARNING
        assert issues[1].line == 7
        assert issues[1].severity == Severity.ERROR

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        ctx = _make_ctx("rust", "main.rs")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cargo", 30)):
            with patch("shutil.which", return_value="/usr/bin/cargo"):
                with patch("tempfile.mkdtemp", return_value="/tmp/clippy_test"):
                    with patch("os.makedirs"):
                        with patch("builtins.open", MagicMock()):
                            with patch("shutil.rmtree"):
                                assert _ClippyAnalyzer().run(ctx) == []

    def test_module_registers_clippy(self):
        # 모듈 임포트 시 REGISTRY에 clippy가 자동 등록된다
        # Module import must auto-register clippy in REGISTRY
        import importlib
        import src.analyzer.io.tools.clippy  # noqa: F401
        importlib.reload(src.analyzer.io.tools.clippy)
        names = [a.name for a in REGISTRY]
        assert "clippy" in names
