"""tflint Terraform 분석기 테스트.
tflint Terraform/HCL analyzer tests.
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


_TFLINT_JSON = json.dumps({"issues": [
    {"message": "Module source uses a git URL without a ref",
     "rule": {"name": "terraform_module_pinned_source", "severity": "warning"},
     "range": {"start": {"line": 5, "column": 1}}},
    {"message": "Missing required attribute",
     "rule": {"name": "terraform_required_version", "severity": "error"},
     "range": {"start": {"line": 12, "column": 1}}},
]})


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


class TestTflintAnalyzer:
    # 🔴 실패 계약(빈 출력·비-봉투·깨진 JSON·OSError)은 어댑터마다 베끼지 않는다 —
    #    `test_sole_observer_fail_closed.py` 가 5개 어댑터에 같은 시험을 건다.
    #    여기 있던 `returns_empty_on_*` 는 그 계약의 **반대**를 보증하고 있었다.
    def test_supports_terraform(self):
        # terraform 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for terraform language
        from src.analyzer.io.tools.tflint import _TflintAnalyzer
        assert _TflintAnalyzer().supports(_make_ctx("terraform", "main.tf"))

    def test_supports_terraform_family_files_through_detect_language(self):
        # 🔴 언어 문자열을 손으로 먹이지 않는다 — 정본 `detect_language()` 를 거친다.
        #    옛 판은 `_make_ctx("hcl", "vars.hcl")` 로 **프로덕션에서 결코 발생하지 않는**
        #    입력을 단언해, 도달 불가한 선언(`"hcl"`)을 초록으로 지켰다 (#1577).
        # Route through the canonical detector: hand-feeding "hcl" asserted an input that
        # production never produces, and kept a dead declaration green.
        from src.analyzer.io.tools.tflint import _TflintAnalyzer
        from src.analyzer.pure.language import detect_language
        analyzer = _TflintAnalyzer()
        for filename in ("vars.hcl", "main.tf"):
            language = detect_language(filename, "")
            assert language == "terraform", f"{filename} -> {language}"
            assert analyzer.supports(_make_ctx(language, filename)), filename

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.tflint import _TflintAnalyzer
        assert not _TflintAnalyzer().supports(_make_ctx("python", "app.py"))

    def test_is_enabled_when_installed(self):
        # tflint 바이너리가 있으면 is_enabled()는 True를 반환한다
        # is_enabled() must return True when tflint binary is present
        from src.analyzer.io.tools.tflint import _TflintAnalyzer
        ctx = _make_ctx("terraform", "main.tf")
        with patch("shutil.which", return_value="/usr/bin/tflint"):
            assert _TflintAnalyzer().is_enabled(ctx) is True

    def test_is_enabled_false_when_missing(self):
        # tflint 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when tflint binary is absent
        from src.analyzer.io.tools.tflint import _TflintAnalyzer
        ctx = _make_ctx("terraform", "main.tf")
        with patch("shutil.which", return_value=None):
            assert _TflintAnalyzer().is_enabled(ctx) is False

    def test_parses_issues(self):
        # tflint JSON 출력의 issues를 파싱해 이슈를 반환해야 한다
        # Must parse issues from tflint JSON output and return AnalysisIssues
        from src.analyzer.io.tools.tflint import _TflintAnalyzer
        ctx = _make_ctx("terraform", "main.tf")
        with patch("subprocess.run") as mock_run:
            with patch("shutil.which", return_value="/usr/bin/tflint"):
                mock_run.return_value = _mock_proc(_TFLINT_JSON, 2)
                issues = _TflintAnalyzer().run(ctx)
        assert len(issues) == 2
        assert issues[0].line == 5
        assert issues[0].severity == Severity.WARNING
        assert issues[1].line == 12
        assert issues[1].severity == Severity.ERROR

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.tflint import _TflintAnalyzer
        ctx = _make_ctx("terraform", "main.tf")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("tflint", 30)):
            with patch("shutil.which", return_value="/usr/bin/tflint"):
                assert _TflintAnalyzer().run(ctx) == []


    def test_module_registers_tflint(self):
        # 모듈 임포트 시 REGISTRY에 tflint가 자동 등록된다
        # Module import must auto-register tflint in REGISTRY
        import importlib
        import src.analyzer.io.tools.tflint  # noqa: F401
        importlib.reload(src.analyzer.io.tools.tflint)
        names = [a.name for a in REGISTRY]
        assert "tflint" in names
