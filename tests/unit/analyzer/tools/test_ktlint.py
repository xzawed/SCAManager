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


# ── ktlint 는 JVM 을 요구한다 (#1578) ─────────────────────────────────────────
#
# 🔴 `railway.toml` 이 받는 릴리스 에셋은 네이티브 실행파일이 아니라 **셸 래퍼**다 —
#    첫 줄이 `#!/bin/sh` 이고 Java 메이저 버전을 탐지해 내장 JAR 를 실행한다(실측: 에셋
#    첫 바이트 직접 조회). 그런데 `nixpacks.toml` 의 `aptPkgs` 에 java 가 없다
#    (`grep -ci "java|jdk|jre"` → railway.toml 0 · nixpacks.toml 0).
#
# 🔴 `which("ktlint")` 는 **참**이다(파일은 있다). 그래서 조달 축이 발화하지 않고 `run()` 이
#    호출되며, JSON 배열이 안 나와 `[]` 로 떨어진다 — 모든 Kotlin 파일이 「이슈 0건 · 완전」.
#    `no_dedicated_observer` 축도 못 잡는다: 어댑터가 `[]` 를 돌려주면 `_run_analyzers` 가
#    정상 실행으로 세기 때문이다.
#
# 🔴 **벽이 아니라 게이트로 만든다.** `#1567` 이 slither/solc 에 한 것과 같은 형태다.
#    fail-closed 로 돌리면 CI(JRE 있음)는 초록이고 프로덕션의 모든 `.kt` 가 `incomplete` 가 된다.
#
# The release asset is a /bin/sh wrapper that requires a JVM; the image provisions none.
# Gate on java so procurement surfaces it instead of silently reporting a clean file.


def _which(present):
    """이름 집합만 PATH 에 있는 `shutil.which` — 나머지는 None."""
    return lambda name: f"/usr/bin/{name}" if name in present else None


class TestKtlintNeedsAJvm:
    def test_ktlint_without_java_is_not_enabled(self):
        """🔴 ktlint 는 있는데 java 가 없다 = 실행할 수 없다."""
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        with patch("src.analyzer.io.tools.ktlint.shutil.which", _which({"ktlint"})):
            assert _KtlintAnalyzer().is_enabled(_make_ctx("kotlin", "Main.kt")) is False

    def test_both_present_still_enabled(self):
        """🔴 부정 통제 — 둘 다 있으면 지금처럼 돈다. 과차단이 이 수정의 위험이다."""
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        with patch("src.analyzer.io.tools.ktlint.shutil.which", _which({"ktlint", "java"})):
            assert _KtlintAnalyzer().is_enabled(_make_ctx("kotlin", "Main.kt")) is True

    def test_java_without_ktlint_is_not_enabled(self):
        """🔴 부정 통제 — java 만 있는 것으로는 켜지지 않는다(게이트가 java 만 보면 안 된다)."""
        from src.analyzer.io.tools.ktlint import _KtlintAnalyzer
        with patch("src.analyzer.io.tools.ktlint.shutil.which", _which({"java"})):
            assert _KtlintAnalyzer().is_enabled(_make_ctx("kotlin", "Main.kt")) is False

    def test_missing_jvm_surfaces_and_does_not_wall(self):
        """🔴 **가장 중요한 단언** — 게이트는 표면화하지 벽이 되면 안 된다.

        `incomplete=True` 가 되면 모든 Kotlin PR 의 auto-merge 가 막힌다. 그것이 #1564 가
        slither 에서 낸 사고이고 세 PR 이 뒤처리에 들어갔다.
        """
        import importlib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
        static = importlib.import_module("src.analyzer.io.static")
        # 🔴 `src…ktlint.shutil` 은 전역 `shutil` 과 **같은 객체**다 — 두 번 패치하면
        #    서로를 덮는다. 한 번만 패치하고 java 만 빼서 그 상태를 만든다.
        # Patch once: the adapter's `shutil` is the global module, not a copy.
        with patch("shutil.which", _which({"ktlint", "semgrep"})), \
                patch("src.analyzer.io.tools.semgrep.subprocess.run",
                      return_value=_mock_proc(json.dumps({"results": [], "errors": []}), 0)):
            result = static.analyze_file("Main.kt", "fun main() {}\n")
        assert result.unavailable_tools == ["ktlint"], (
            f"조달 축으로 가야 한다 — unavailable={result.unavailable_tools}"
        )
        assert result.incomplete is False, "🔴 벽이 됐다 — 모든 Kotlin 이 incomplete 다"
        assert result.no_dedicated_observer == "kotlin", (
            "전담이 하나도 안 돌았음이 기록돼야 한다"
        )
