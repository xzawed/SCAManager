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

from src.analyzer.registry import AnalyzeContext  # noqa: E402
from src.analyzer.tools.cppcheck import _CppCheckAnalyzer, _parse_cppcheck_xml  # noqa: E402


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
    with patch("src.analyzer.tools.cppcheck.shutil.which", return_value=None):
        assert _CppCheckAnalyzer().is_enabled(_ctx()) is False


def test_is_enabled_when_binary_present():
    with patch("src.analyzer.tools.cppcheck.shutil.which", return_value="/usr/bin/cppcheck"):
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
    with patch("src.analyzer.tools.cppcheck.subprocess.run", return_value=mock_result):
        issues = _CppCheckAnalyzer().run(_ctx("c"))
    assert len(issues) == 2
    assert issues[0].tool == "cppcheck"


def test_run_returns_empty_on_timeout():
    with patch(
        "src.analyzer.tools.cppcheck.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="cppcheck", timeout=30),
    ):
        assert _CppCheckAnalyzer().run(_ctx()) == []


def test_run_returns_empty_on_oserror():
    with patch(
        "src.analyzer.tools.cppcheck.subprocess.run",
        side_effect=OSError("not found"),
    ):
        assert _CppCheckAnalyzer().run(_ctx()) == []


def test_run_returns_empty_on_xml_parse_error():
    mock_result = MagicMock()
    mock_result.stderr = "not xml at all <<<"
    mock_result.stdout = ""
    with patch("src.analyzer.tools.cppcheck.subprocess.run", return_value=mock_result):
        assert _CppCheckAnalyzer().run(_ctx()) == []


def test_run_empty_stderr_returns_empty():
    mock_result = MagicMock()
    mock_result.stderr = ""
    mock_result.stdout = ""
    with patch("src.analyzer.tools.cppcheck.subprocess.run", return_value=mock_result):
        assert _CppCheckAnalyzer().run(_ctx()) == []
