"""_SlitherAnalyzer 단위 테스트 — JSON 파싱 + subprocess mock (Phase D.2)."""
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


def test_parse_json_returns_empty_when_compilation_failed():
    assert _parse_slither_json(_JSON_COMPILATION_FAILED, language="solidity") == []


# ── _SlitherAnalyzer.run (subprocess mock) ─────────────────────────────


def test_run_returns_empty_on_timeout():
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="slither", timeout=30),
    ):
        assert _SlitherAnalyzer().run(_ctx()) == []


def test_run_returns_empty_on_oserror():
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        side_effect=OSError("not found"),
    ):
        assert _SlitherAnalyzer().run(_ctx()) == []


def test_run_returns_empty_on_json_decode_error():
    mock_result = MagicMock()
    mock_result.stdout = "not valid json {{{"
    mock_result.stderr = ""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        return_value=mock_result,
    ):
        assert _SlitherAnalyzer().run(_ctx()) == []


def test_run_returns_empty_on_schema_variant_results_list():
    """slither JSON 스키마가 변형되어 results 가 list 면 AttributeError → []."""
    mock_result = MagicMock()
    mock_result.stdout = '{"success": true, "results": ["unexpected list shape"]}'
    mock_result.stderr = ""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        return_value=mock_result,
    ):
        assert _SlitherAnalyzer().run(_ctx()) == []


def test_run_empty_stdout_returns_empty():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = ""
    with patch(
        "src.analyzer.io.tools.slither.subprocess.run",
        return_value=mock_result,
    ):
        assert _SlitherAnalyzer().run(_ctx()) == []
