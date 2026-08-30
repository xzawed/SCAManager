"""hadolint Dockerfile 분석기 테스트.
hadolint Dockerfile analyzer tests.
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


# ── 크래시가 «이슈 0건» 이 되던 자리 (#1557 W2 — CI 실측 기반) ──────────────────
#
# 🔴 CI 실바이너리 실측(`tests/integration/…::W2-SHAPE`):
#
#      깨끗              exit=0 · stdout `[]`
#      깨진 Dockerfile    exit=1 · stdout JSON 배열 + `DL1000`  ← **발견**이지 크래시가 아니다
#      없는 경로(크래시)  exit=1 · stdout **0자** · stderr `withBinaryFile: does not exist`
#
#    즉 **성공하면 항상 JSON 배열을 낸다**(깨끗해도 `[]`). 판별식은 「stdout 이 비었다」이고,
#    깨진 입력은 발견으로 나오므로 이 판별식에 걸리지 않는다(과차단 없음).
#
# 🔴 `dockerfile` 은 조달된 전담 관측면이 hadolint **하나뿐**이다. `[]` 를 돌려주면
#    미분석 Dockerfile 이 «이슈 0건 · 완전» 으로 기록된다.
#
# Measured in CI: a successful run always emits a JSON array (`[]` when clean), so empty stdout
# is the discriminant; a broken Dockerfile is a finding (DL1000), not a crash.


def _proc2(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=["hadolint"], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


class TestHadolintCrashIsNotACleanFile:
    def test_empty_stdout_raises(self):
        """🔴 배열이 없다 = 분석하지 못했다. 실측: 없는 경로 → exit=1 · stdout 0자."""
        crash = _proc2(stderr="hadolint: /x/Dockerfile: withBinaryFile: does not exist\n",
                       returncode=1)
        with patch("subprocess.run", return_value=crash):
            with pytest.raises(RuntimeError, match="hadolint"):
                _hadolint().run(_make_ctx("dockerfile", "Dockerfile"))

    def test_clean_empty_array_is_still_clean(self):
        """🔴 부정 통제 — `[]` 는 깨끗함이다. 여기서 raise 하면 모든 Dockerfile 이 막힌다."""
        with patch("subprocess.run", return_value=_proc2(stdout="[]", returncode=0)):
            assert _hadolint().run(_make_ctx("dockerfile", "Dockerfile")) == []

    def test_broken_dockerfile_is_a_finding_not_a_crash(self):
        """🔴 부정 통제 — 실측대로 깨진 입력은 `DL1000` 발견으로 나온다(exit=1 이어도)."""
        payload = json.dumps([{"code": "DL1000", "level": "error", "line": 1,
                               "message": "unexpected end of input"}])
        with patch("subprocess.run", return_value=_proc2(stdout=payload, returncode=1)):
            issues = _hadolint().run(_make_ctx("dockerfile", "Dockerfile"))
        assert len(issues) == 1 and issues[0].tool == "hadolint"

    def test_unparsable_json_raises(self):
        """🔴 무언가를 냈는데 읽을 수 없다 = 미분석이다."""
        with patch("subprocess.run", return_value=_proc2(stdout="not json", returncode=1)):
            with pytest.raises(RuntimeError, match="hadolint"):
                _hadolint().run(_make_ctx("dockerfile", "Dockerfile"))

    def test_missing_binary_is_procurement_not_crash(self):
        """🔴 which() 통과 뒤 사라진 바이너리는 조달 축이 담당한다 — `[]` 유지."""
        with patch("subprocess.run", side_effect=FileNotFoundError("hadolint")):
            assert _hadolint().run(_make_ctx("dockerfile", "Dockerfile")) == []

    def test_timeout_is_not_a_crash(self):
        """🔴 타임아웃은 `ctx.timed_out` 이 담당한다."""
        ctx = _make_ctx("dockerfile", "Dockerfile")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("hadolint", 30)):
            assert _hadolint().run(ctx) == []
        assert ctx.timed_out is True


def _hadolint():
    """등록부에서 꺼낸다 — `from … import` 와 `import …` 가 한 파일에 공존하지 않게 한다."""
    return next(a for a in REGISTRY if a.name == "hadolint")
