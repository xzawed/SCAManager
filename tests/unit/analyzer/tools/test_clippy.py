"""clippy Rust 분석기 테스트.
clippy Rust analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, REGISTRY


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
        # 🔴 plain `import src…` 를 쓰지 않는다 — 이 파일이 `from src… import` 도 쓰므로
        #    공존하면 CodeQL py/import-and-import-from 을 자초한다(`check_dual_import.py`).
        # Use the string path: a plain import alongside `from X import` self-inflicts the alert.
        import importlib
        importlib.reload(importlib.import_module("src.analyzer.io.tools.clippy"))
        names = [a.name for a in REGISTRY]
        assert "clippy" in names


# ──────────────────────────────────────────────────────────────────────────────
# 크래시가 «이슈 0건» 이 되던 자리 (#1557 W2 — 실측 기반)
#
# 🔴 판별식은 도구마다 다르다. 이 리포의 관용구(「비-JSON stdout 이면 raise」)를
#    그대로 복사하면 이 도구의 크래시를 **못 잡는다** — 아래 실측이 그것을 보여준다.
# ──────────────────────────────────────────────────────────────────────────────


class TestClippyCrashIsNotACleanRun:
    """🔴 실측(clippy 0.1.97, 임시 cargo 프로젝트):

        깨끗 · 린트 있음        exit=0   · stdout **비지 않음** (줄 수는 캐시 상태에 따라 다르다)
        컴파일 오류(정당)        exit=**101** · stdout **비지 않음**
        크래시(Cargo.toml 없음)  exit=**101** · stdout **0줄**

    정당한 컴파일 오류와 크래시가 **둘 다 exit 101** 이다 — exit 은 판별식이 아니다.
    성공하면 깨끗해도 JSONL 을 내므로 판별식은 **빈 stdout** 이다.
    Measured: a legitimate compile error and a crash share exit 101; only stdout differs.
    """

    def test_empty_stdout_is_a_crash(self):
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        proc = MagicMock(stdout="", stderr="error: could not find `Cargo.toml`", returncode=101)
        with patch("src.analyzer.io.tools.clippy._build_temp_cargo_project", return_value="/tmp/x"):
            with patch("subprocess.run", return_value=proc):
                with pytest.raises(RuntimeError, match="clippy"):
                    _ClippyAnalyzer().run(_make_ctx("rust", "main.rs"))

    def test_compile_error_at_exit_101_is_not_a_crash(self):
        """🔴 부정 통제 — 컴파일 오류는 **정당한 발견**이다. exit 으로 판정하면 차단된다."""
        from src.analyzer.io.tools.clippy import _ClippyAnalyzer
        # 🔴 리스트 안에서 인접 문자열 리터럴을 붙이지 않는다 — 쉼표 누락과 구별되지 않아
        #    CodeQL py/implicit-string-concatenation-in-list 가 발화한다(#608, 자초).
        # Build the line first: implicit concatenation inside a list reads as a missing comma.
        compiler_message = json.dumps({
            "reason": "compiler-message",
            "message": {"level": "error", "message": "mismatched types",
                        "code": None, "spans": []},
        })
        build_finished = json.dumps({"reason": "build-finished", "success": False})
        jsonl = compiler_message + "\n" + build_finished + "\n"
        proc = MagicMock(stdout=jsonl, stderr="", returncode=101)
        with patch("src.analyzer.io.tools.clippy._build_temp_cargo_project", return_value="/tmp/x"):
            with patch("subprocess.run", return_value=proc):
                _ClippyAnalyzer().run(_make_ctx("rust", "main.rs"))  # raise 하지 않는다
