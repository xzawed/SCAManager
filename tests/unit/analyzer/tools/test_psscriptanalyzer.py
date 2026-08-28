"""psscriptanalyzer PowerShell 분석기 테스트.
psscriptanalyzer PowerShell analyzer tests.
"""
import json
import subprocess
import pytest
from unittest.mock import patch, MagicMock
from src.analyzer.pure.registry import AnalyzeContext, Severity, Category, REGISTRY


def _make_ctx(filename: str = "script.ps1", language: str = "powershell",
              content: str = "Write-Host 'Hello'") -> AnalyzeContext:
    return AnalyzeContext(
        filename=filename, content=content, language=language,
        is_test=False, tmp_path=f"/tmp/{filename}",
    )


def _mock_proc(stdout: str = "", returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.stdout = stdout
    m.stderr = ""
    m.returncode = returncode
    return m


_PSSA_JSON = json.dumps([
    {
        "Message": "Avoid using Write-Host.",
        "Line": 1,
        "Severity": 2,
        "RuleName": "PSAvoidUsingWriteHost",
    },
    {
        "Message": "Script should use approved verbs.",
        "Line": 5,
        "Severity": 1,
        "RuleName": "PSUseApprovedVerbs",
    },
])


@pytest.fixture(autouse=True)
def _isolate_registry():
    """REGISTRY를 각 테스트마다 초기화한다.
    Reset REGISTRY for each test.
    """
    original = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(original)


class TestPSScriptAnalyzer:
    # 🔴 실패 계약(빈 출력·비-봉투·깨진 JSON·OSError)은 어댑터마다 베끼지 않는다 —
    #    `test_sole_observer_fail_closed.py` 가 5개 어댑터에 같은 시험을 건다.
    #    여기 있던 `returns_empty_on_*` 는 그 계약의 **반대**를 보증하고 있었다.
    def test_supports_powershell(self):
        # powershell 언어는 supports()가 True를 반환해야 한다
        # supports() must return True for powershell language
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        assert _PSScriptAnalyzer().supports(_make_ctx("script.ps1", "powershell"))

    def test_does_not_support_python(self):
        # python 언어는 supports()가 False를 반환해야 한다
        # supports() must return False for python language
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        assert not _PSScriptAnalyzer().supports(_make_ctx("app.py", "python"))

    def test_is_enabled_when_installed(self):
        # 🔴 pwsh 존재만으로는 부족하다 — PSScriptAnalyzer 모듈은 별도 설치다.
        #    모듈 축의 시험은 `test_sole_observer_fail_closed.py` 에 있다.
        # The pwsh binary alone is not the capability; the module ships separately.
        from src.analyzer.io.tools import psscriptanalyzer as m
        ctx = _make_ctx()
        m.psscriptanalyzer_module_available.cache_clear()
        try:
            with patch("shutil.which", return_value="/usr/bin/pwsh"):
                with patch("subprocess.run", return_value=_mock_proc("PSScriptAnalyzer\n", 0)):
                    assert m._PSScriptAnalyzer().is_enabled(ctx) is True
        finally:
            m.psscriptanalyzer_module_available.cache_clear()

    def test_is_enabled_false_when_missing(self):
        # pwsh 바이너리가 없으면 is_enabled()는 False를 반환한다
        # is_enabled() must return False when pwsh binary is absent
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("shutil.which", return_value=None):
            assert _PSScriptAnalyzer().is_enabled(ctx) is False

    def test_parses_json_array(self):
        # PSScriptAnalyzer JSON 배열 출력을 파싱해 이슈를 반환해야 한다
        # Must parse PSScriptAnalyzer JSON array output and return issues
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", return_value=_mock_proc(_PSSA_JSON)):
            issues = _PSScriptAnalyzer().run(ctx)
        assert len(issues) == 2
        # Severity 2 → WARNING
        assert issues[0].severity == Severity.WARNING
        assert issues[0].line == 1
        assert issues[0].message == "Avoid using Write-Host."
        assert issues[0].category == Category.CODE_QUALITY
        # Severity 1 → ERROR
        assert issues[1].severity == Severity.ERROR
        assert issues[1].line == 5

    def test_severity_string_error(self):
        # Severity가 문자열 "Error"인 경우 Severity.ERROR를 반환해야 한다
        # Must return Severity.ERROR when Severity is the string "Error"
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        data = json.dumps([{"Message": "Bad verb.", "Line": 2, "Severity": "Error"}])
        with patch("subprocess.run", return_value=_mock_proc(data)):
            issues = _PSScriptAnalyzer().run(ctx)
        assert len(issues) == 1
        assert issues[0].severity == Severity.ERROR

    def test_returns_empty_on_timeout(self):
        # subprocess TimeoutExpired 시 빈 목록을 반환해야 한다
        # Must return empty list on subprocess TimeoutExpired
        from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer
        ctx = _make_ctx()
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("pwsh", 30)):
            assert _PSScriptAnalyzer().run(ctx) == []





    def test_module_registers_psscriptanalyzer(self):
        # 모듈 임포트 시 REGISTRY에 psscriptanalyzer가 자동 등록된다
        # Module import must auto-register psscriptanalyzer in REGISTRY
        import importlib
        import src.analyzer.io.tools.psscriptanalyzer  # noqa: F401
        importlib.reload(src.analyzer.io.tools.psscriptanalyzer)
        names = [a.name for a in REGISTRY]
        assert "psscriptanalyzer" in names
