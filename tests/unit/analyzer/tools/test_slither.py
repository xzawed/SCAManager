"""_SlitherAnalyzer 단위 테스트 — JSON 파싱 + subprocess mock (Phase D.2)."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import subprocess  # noqa: E402
import pytest  # noqa: E402
from unittest.mock import MagicMock, patch  # noqa: E402

from src.analyzer.pure.registry import AnalyzeContext  # noqa: E402
from src.analyzer.io.tools.slither import (  # noqa: E402
    _SlitherAnalyzer,
    _parse_slither_json,
)


_JSON_REENTRANCY = """
{
  "success": true,
  "results": {
    "detectors": [
      {
        "check": "reentrancy-eth",
        "impact": "High",
        "description": "Reentrancy in Vault.withdraw: external call before state update",
        "elements": [{"source_mapping": {"lines": [42]}}]
      },
      {
        "check": "pragma",
        "impact": "Informational",
        "description": "Multiple Solidity versions used",
        "elements": [{"source_mapping": {"lines": [1]}}]
      }
    ]
  }
}
"""

_JSON_MEDIUM_IMPACT = """
{
  "success": true,
  "results": {
    "detectors": [
      {
        "check": "unchecked-transfer",
        "impact": "Medium",
        "description": "Transfer return value not checked",
        "elements": [{"source_mapping": {"lines": [15]}}]
      }
    ]
  }
}
"""

_JSON_LOW_IMPACT = """
{
  "success": true,
  "results": {
    "detectors": [
      {
        "check": "naming-convention",
        "impact": "Low",
        "description": "Contract naming does not follow convention",
        "elements": [{"source_mapping": {"lines": [3]}}]
      }
    ]
  }
}
"""

_JSON_COMPILATION_FAILED = '{"success": false, "error": "solc error"}'

_JSON_NO_ELEMENTS = """
{
  "success": true,
  "results": {
    "detectors": [
      {
        "check": "pragma",
        "impact": "Informational",
        "description": "no location",
        "elements": []
      }
    ]
  }
}
"""


def _ctx(language: str = "solidity") -> AnalyzeContext:
    return AnalyzeContext(
        filename="Vault.sol",
        content="// SPDX-License-Identifier: MIT\npragma solidity ^0.8.0;\ncontract Vault {}",
        language=language,
        is_test=False,
        tmp_path="/tmp/Vault.sol",  # nosec B108
    )


# ── supports / is_enabled ───────────────────────────────────────────────


def test_supports_solidity():
    assert _SlitherAnalyzer().supports(_ctx("solidity")) is True


def test_supports_rejects_other_languages():
    a = _SlitherAnalyzer()
    assert a.supports(_ctx("python")) is False
    assert a.supports(_ctx("c")) is False
    assert a.supports(_ctx("cpp")) is False
    assert a.supports(_ctx("unknown")) is False


def test_is_enabled_when_binary_missing():
    with patch("src.analyzer.io.tools.slither.shutil.which", return_value=None):
        assert _SlitherAnalyzer().is_enabled(_ctx()) is False


def test_is_enabled_when_binary_present():
    with patch(
        "src.analyzer.io.tools.slither.shutil.which",
        return_value="/usr/local/bin/slither",
    ):
        assert _SlitherAnalyzer().is_enabled(_ctx()) is True


# ── _parse_slither_json ────────────────────────────────────────────────


def test_parse_json_extracts_detectors():
    issues = _parse_slither_json(_JSON_REENTRANCY, language="solidity")
    assert len(issues) == 2
    assert all(i.tool == "slither" for i in issues)
    assert all(i.language == "solidity" for i in issues)


def test_parse_json_maps_high_impact_to_error():
    issues = _parse_slither_json(_JSON_REENTRANCY, language="solidity")
    reentrancy = next(i for i in issues if "Reentrancy" in i.message)
    assert reentrancy.severity == "error"
    assert reentrancy.line == 42


def test_parse_json_maps_medium_impact_to_error():
    issues = _parse_slither_json(_JSON_MEDIUM_IMPACT, language="solidity")
    assert issues[0].severity == "error"


def test_parse_json_maps_low_impact_to_warning():
    issues = _parse_slither_json(_JSON_LOW_IMPACT, language="solidity")
    assert issues[0].severity == "warning"


def test_parse_json_assigns_security_category_for_reentrancy():
    issues = _parse_slither_json(_JSON_REENTRANCY, language="solidity")
    reentrancy = next(i for i in issues if "Reentrancy" in i.message)
    assert reentrancy.category == "security"


def test_parse_json_assigns_code_quality_for_other_checks():
    issues = _parse_slither_json(_JSON_REENTRANCY, language="solidity")
    pragma = next(i for i in issues if "Multiple" in i.message)
    assert pragma.category == "code_quality"


def test_parse_json_extracts_line_from_source_mapping():
    issues = _parse_slither_json(_JSON_REENTRANCY, language="solidity")
    pragma = next(i for i in issues if "Multiple" in i.message)
    assert pragma.line == 1


def test_parse_json_missing_elements_defaults_line_to_zero():
    issues = _parse_slither_json(_JSON_NO_ELEMENTS, language="solidity")
    assert len(issues) == 1
    assert issues[0].line == 0


def test_parse_json_raises_when_compilation_failed():
    """🔴 계약 변경(#1557 W2) — `success=false` 는 slither 자신이 「분석 못 했다」고
    보고한 것이다. `[]` 로 돌려주면 그 침묵이 «이슈 0건 · 완전» 이 된다."""
    with pytest.raises(ValueError, match="success=false"):
        _parse_slither_json(_JSON_COMPILATION_FAILED, language="solidity")


# ── _SlitherAnalyzer.run (subprocess mock) ─────────────────────────────


def test_run_returns_empty_on_timeout():
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="slither", timeout=30),
    ):
        assert _SlitherAnalyzer().run(_ctx()) == []


def test_run_propagates_non_filenotfound_oserror():
    """🔴 계약 변경(#1557 W2) — which() 통과 후의 실행 실패는 미분석이라 올라간다.
    바이너리 부재(FileNotFoundError)만 조달 축으로 `[]` 다."""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        side_effect=PermissionError("permission denied"),
    ):
        with pytest.raises(OSError):
            _SlitherAnalyzer().run(_ctx())


def test_run_returns_empty_on_binary_missing():
    """부정 통제 — 바이너리 부재는 조달 축이므로 그대로 `[]`."""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        side_effect=FileNotFoundError("slither not found"),
    ):
        assert _SlitherAnalyzer().run(_ctx()) == []


def test_run_raises_on_json_decode_error():
    mock_result = MagicMock()
    mock_result.stdout = "not valid json {{{"
    mock_result.stderr = ""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        return_value=mock_result,
    ):
        with pytest.raises(RuntimeError, match="slither"):
            _SlitherAnalyzer().run(_ctx())


def test_run_raises_on_schema_variant_results_list():
    """🔴 스키마 변형은 **미분석**이다 — 읽을 수 없는 출력을 «이슈 0건» 으로 기록하지 않는다."""
    mock_result = MagicMock()
    mock_result.stdout = '{"success": true, "results": ["unexpected list shape"]}'
    mock_result.stderr = ""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        return_value=mock_result,
    ):
        with pytest.raises(RuntimeError, match="slither"):
            _SlitherAnalyzer().run(_ctx())


def test_run_raises_on_empty_stdout():
    """🔴 성공하면 항상 JSON 을 낸다(실측) — 빈 stdout 은 미분석이다."""
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        return_value=mock_result,
    ):
        with pytest.raises(RuntimeError, match="slither"):
            _SlitherAnalyzer().run(_ctx())


# ──────────────────────────────────────────────────────────────────────────────
# 크래시가 «이슈 0건» 이 되던 자리 (#1557 W2 — 실측 기반)
#
# 🔴 판별식은 도구마다 다르다. 이 리포의 관용구(「비-JSON stdout 이면 raise」)를
#    그대로 복사하면 이 도구의 크래시를 **못 잡는다** — 아래 실측이 그것을 보여준다.
# ──────────────────────────────────────────────────────────────────────────────


class TestSlitherCrashIsNotACleanRun:
    """🔴 실측(slither, 이 호스트):

        유효한 .sol      exit=**127** · stdout=2437자 · JSON success=true
        구문 오류        exit=1   · stdout=**0자**
        없는 파일        exit=1   · stdout=**0자**

    성공해도 exit 이 0 이 아니다 — **exit code 는 판별식이 될 수 없다**.
    성공하면 항상 JSON 을 내므로 판별식은 **빈 stdout** 이다.
    Measured: a successful slither run exits 127 with JSON; a crash writes nothing.
    """

    def test_empty_stdout_is_a_crash(self):
        from src.analyzer.io.tools.slither import _SlitherAnalyzer
        proc = MagicMock(stdout="", stderr="Traceback ...", returncode=1)
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(RuntimeError, match="slither"):
                _SlitherAnalyzer().run(_ctx())

    def test_nonzero_exit_with_json_is_not_a_crash(self):
        """🔴 부정 통제 — 성공이 exit 127 이다. exit 으로 판정하면 정상 실행이 차단된다."""
        from src.analyzer.io.tools.slither import _SlitherAnalyzer
        ok = '{"success": true, "results": {"detectors": []}}'
        proc = MagicMock(stdout=ok, stderr="", returncode=127)
        with patch("subprocess.run", return_value=proc):
            assert _SlitherAnalyzer().run(_ctx()) == []
