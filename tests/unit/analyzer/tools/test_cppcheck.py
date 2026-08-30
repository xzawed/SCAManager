"""_CppCheckAnalyzer 단위 테스트 — XML 파싱 + subprocess mock."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import subprocess  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

from src.analyzer.pure.registry import AnalyzeContext  # noqa: E402
from src.analyzer.io.tools.cppcheck import _CppCheckAnalyzer, _parse_cppcheck_xml  # noqa: E402


_XML_TWO_ERRORS = """<?xml version="1.0" encoding="UTF-8"?>
<results version="2">
  <errors>
    <error id="nullPointer" severity="error" msg="Null pointer dereference">
      <location file="test.c" line="10"/>
    </error>
    <error id="variableScope" severity="style" msg="Variable scope can be reduced">
      <location file="test.c" line="25"/>
    </error>
  </errors>
</results>
"""

_XML_EMPTY = """<?xml version="1.0" encoding="UTF-8"?>
<results version="2"><errors/></results>
"""


def _ctx(language: str = "c") -> AnalyzeContext:
    return AnalyzeContext(
        filename="test.c",
        content="int main(){return 0;}",
        language=language,
        is_test=False,
        tmp_path="/tmp/test.c",
    )


# ── supports / is_enabled ───────────────────────────────────────────────


def test_supports_c_language():
    assert _CppCheckAnalyzer().supports(_ctx("c")) is True


def test_supports_cpp_language():
    assert _CppCheckAnalyzer().supports(_ctx("cpp")) is True


def test_supports_rejects_other_languages():
    a = _CppCheckAnalyzer()
    assert a.supports(_ctx("python")) is False
    assert a.supports(_ctx("shell")) is False
    assert a.supports(_ctx("unknown")) is False


def test_is_enabled_when_binary_missing():
    with patch("src.analyzer.io.tools.cppcheck.shutil.which", return_value=None):
        assert _CppCheckAnalyzer().is_enabled(_ctx()) is False


def test_is_enabled_when_binary_present():
    with patch("src.analyzer.io.tools.cppcheck.shutil.which", return_value="/usr/bin/cppcheck"):
        assert _CppCheckAnalyzer().is_enabled(_ctx()) is True


# ── _parse_cppcheck_xml ────────────────────────────────────────────────


def test_parse_xml_extracts_both_severities():
    issues = _parse_cppcheck_xml(_XML_TWO_ERRORS, language="c")
    assert len(issues) == 2
    assert issues[0].tool == "cppcheck"
    assert issues[0].severity == "error"
    assert issues[0].category == "code_quality"
    assert issues[0].language == "c"
    assert issues[0].line == 10
    assert "Null pointer" in issues[0].message


def test_parse_xml_maps_style_to_warning():
    issues = _parse_cppcheck_xml(_XML_TWO_ERRORS, language="c")
    assert issues[1].severity == "warning"
    assert issues[1].line == 25


def test_parse_xml_empty_returns_empty_list():
    assert _parse_cppcheck_xml(_XML_EMPTY, language="c") == []


def test_parse_xml_missing_location_line_defaults_to_zero():
    xml = """<?xml version="1.0"?>
<results version="2"><errors>
  <error id="x" severity="warning" msg="no loc"/>
</errors></results>"""
    issues = _parse_cppcheck_xml(xml, language="cpp")
    assert len(issues) == 1
    assert issues[0].line == 0
    assert issues[0].language == "cpp"


# ── _CppCheckAnalyzer.run (subprocess mock) ─────────────────────────────


def test_run_parses_stderr_xml():
    """cppcheck 는 XML 을 stderr 에 출력 — stdout 이 비어 있어도 파싱 성공."""
    mock_result = MagicMock()
    mock_result.stderr = _XML_TWO_ERRORS
    mock_result.stdout = ""
    with patch("src.analyzer.io.tools.cppcheck.subprocess.run", return_value=mock_result):
        issues = _CppCheckAnalyzer().run(_ctx("c"))
    assert len(issues) == 2
    assert issues[0].tool == "cppcheck"


def test_run_returns_empty_on_timeout():
    with patch(
        "src.analyzer.io.tools.cppcheck.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="cppcheck", timeout=30),
    ):
        assert _CppCheckAnalyzer().run(_ctx()) == []


def test_run_returns_empty_on_oserror():
    with patch(
        "src.analyzer.io.tools.cppcheck.subprocess.run",
        side_effect=OSError("not found"),
    ):
        assert _CppCheckAnalyzer().run(_ctx()) == []


def test_run_returns_empty_on_xml_parse_error():
    mock_result = MagicMock()
    mock_result.stderr = "not xml at all <<<"
    mock_result.stdout = ""
    with patch("src.analyzer.io.tools.cppcheck.subprocess.run", return_value=mock_result):
        assert _CppCheckAnalyzer().run(_ctx()) == []


def test_run_empty_stderr_returns_empty():
    mock_result = MagicMock()
    mock_result.stderr = ""
    mock_result.stdout = ""
    with patch("src.analyzer.io.tools.cppcheck.subprocess.run", return_value=mock_result):
        assert _CppCheckAnalyzer().run(_ctx()) == []


# ── 크래시가 «이슈 0건» 이 되던 자리 (#1557 W2 — CI 실측 기반) ──────────────────
#
# 🔴 cppcheck 는 **stderr 가 결과 채널**이다(그 관례 때문에 어댑터도 stderr 를 읽는다).
#    CI 실바이너리 실측(cppcheck 2.13.0, `tests/integration/…::W2-SHAPE`):
#
#      깨끗              exit=0 · stderr = `<results version="2">…<errors></errors></results>`
#      구문 오류(발견)    exit=0 · stderr = 같은 봉투 + `<error id="syntaxError" …>`
#      없는 경로(크래시)  exit=1 · stderr **0자** · stdout 평문
#                        `cppcheck: error: could not find or open any of the paths given.`
#
#    즉 **성공하면 항상 봉투를 낸다.** 그래서 판별식은 「stderr 가 비었다」이고,
#    깨진 입력은 크래시가 아니라 **발견**이라 이 판별식에 걸리지 않는다(과차단 없음).
#
# 🔴 `c`·`cpp` 는 조달된 전담 관측면이 cppcheck **하나뿐**이다. 여기서 `[]` 를 돌려주면
#    미분석 C/C++ 가 «이슈 0건 · 완전» 으로 기록되고 정적 만점으로 auto-merge 된다 —
#    `no_dedicated_observer` 축도 못 잡는다(어댑터가 「돌긴 했다」로 세어진다).
#
# Measured in CI: a successful run always emits the XML envelope on stderr, so empty stderr
# is the discriminant; broken input is reported as a finding, not a crash.

_XML_CLEAN = ('<?xml version="1.0" encoding="UTF-8"?>\n'
              '<results version="2">\n  <cppcheck version="2.13.0"/>\n'
              '  <errors>\n  </errors>\n</results>\n')
_XML_FINDING = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<results version="2">\n  <cppcheck version="2.13.0"/>\n'
                '  <errors>\n'
                '    <error id="nullPointer" severity="error" msg="Null pointer dereference">\n'
                '      <location file="a.cpp" line="3"/>\n'
                '    </error>\n'
                '  </errors>\n</results>\n')


def _proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    return subprocess.CompletedProcess(args=["cppcheck"], returncode=returncode,
                                       stdout=stdout, stderr=stderr)


class TestCppcheckCrashIsNotACleanFile:
    def test_empty_stderr_raises(self):
        """🔴 봉투가 없다 = 분석하지 못했다. 실측: 없는 경로 → exit=1 · stderr 0자."""
        crash = _proc(stdout="cppcheck: error: could not find or open any of the paths given.\n",
                      returncode=1)
        with patch("subprocess.run", return_value=crash):
            with pytest.raises(RuntimeError, match="cppcheck"):
                _CppCheckAnalyzer().run(_ctx("cpp"))

    def test_clean_envelope_is_still_clean(self):
        """🔴 부정 통제 — 깨끗한 봉투는 `[]` 다. 여기서 raise 하면 모든 C/C++ 가 막힌다."""
        with patch("subprocess.run", return_value=_proc(stderr=_XML_CLEAN, returncode=0)):
            assert _CppCheckAnalyzer().run(_ctx("cpp")) == []

    def test_findings_still_parse(self):
        """🔴 부정 통제 — 발견은 그대로 읽힌다."""
        with patch("subprocess.run", return_value=_proc(stderr=_XML_FINDING, returncode=0)):
            issues = _CppCheckAnalyzer().run(_ctx("cpp"))
        assert len(issues) == 1 and issues[0].tool == "cppcheck"

    def test_unparsable_xml_raises(self):
        """🔴 봉투가 있는데 읽을 수 없다 = 미분석이다 — 조용히 `[]` 로 흘리지 않는다."""
        with patch("subprocess.run", return_value=_proc(stderr="<results version=", returncode=0)):
            with pytest.raises(RuntimeError, match="cppcheck"):
                _CppCheckAnalyzer().run(_ctx("cpp"))

    def test_missing_binary_is_procurement_not_crash(self):
        """🔴 which() 통과 뒤 사라진 바이너리는 조달 축이 담당한다 — `[]` 유지."""
        with patch("subprocess.run", side_effect=FileNotFoundError("cppcheck")):
            assert _CppCheckAnalyzer().run(_ctx("cpp")) == []

    def test_timeout_is_not_a_crash(self):
        """🔴 타임아웃은 `ctx.timed_out` 이 담당한다 — 기존 계약 유지."""
        ctx = _ctx("cpp")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cppcheck", 30)):
            assert _CppCheckAnalyzer().run(ctx) == []
        assert ctx.timed_out is True
