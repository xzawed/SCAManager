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

        유효한 .sol      exit **비-0** · stdout 에 JSON success=true
        구문 오류·없는 파일  stdout=**0자**

    성공해도 exit 이 0 이 아니다 — **exit code 는 판별식이 될 수 없다**.
    (같은 성공을 두 호스트에서 재니 127 과 4294967295 였다. 값은 우연이다.)
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


# ── 조달 축: solc 컴파일러 (#1566 회고 P1) ──────────────────────────────────
#
# 🔴 slither 는 pip 패키지라 `which("slither")` 는 solc 유무와 무관하게 참이다.
#    `railway.toml` 은 `solc-select install` 이 실패하면 「slither analyzer will be
#    disabled」라고 적지만 그 비활성화가 구현된 적이 없다. 그래서 solc 가 없으면
#    slither 가 **실행되어** 빈 stdout 을 내고, 그것을 미분석으로 올리는 순간
#    모든 Solidity 파일이 `incomplete` 가 된다 — 조달 실패가 게이트가 아니라 벽이 된다.
#
# 실측 (slither 0.11.5, `--solc` 로 컴파일러만 격리):
#     정상 solc      exit=127 · stdout 1773자 · success=true
#     solc 사용 불가  exit=1   · stdout **0자**      ← `success:false` 가 아니다
#
# 🔴 그리고 `shutil.which("solc")` 는 프로브가 **될 수 없다** — `solc` 는
#    solc-select 1.2.0 이 까는 콘솔 스크립트(`solc_select.__main__:solc`)이고
#    `slither-analyzer → crytic-compile → solc-select` 의존이라 pip 설치만으로
#    항상 PATH 에 생긴다. 컴파일러 아티팩트 유무를 봐야 한다.


def _enabled_with(monkeypatch, *, slither_path, installed):
    """`is_enabled` 를 조달 상태만 바꿔 태운다 — 네트워크를 타지 않는다."""
    import sys as _sys
    import types
    monkeypatch.setattr("src.analyzer.io.tools.slither.shutil.which",
                        lambda name: slither_path if name == "slither" else "/usr/bin/solc")
    mod = types.ModuleType("solc_select.solc_select")
    mod.installed_versions = lambda: installed
    pkg = types.ModuleType("solc_select")
    monkeypatch.setitem(_sys.modules, "solc_select", pkg)
    monkeypatch.setitem(_sys.modules, "solc_select.solc_select", mod)
    return _SlitherAnalyzer().is_enabled(_ctx())


def test_disabled_when_no_solc_version_is_installed(monkeypatch):
    """🔴 조달 실패 — 컴파일러 아티팩트가 없으면 실행하지 않는다(벽이 아니라 게이트)."""
    assert _enabled_with(monkeypatch, slither_path="/usr/bin/slither", installed=[]) is False


def test_enabled_when_a_solc_version_is_installed(monkeypatch):
    """🔴 부정 통제 — 아티팩트가 있으면 그대로 돈다. 과차단하면 Solidity 분석이 사라진다."""
    assert _enabled_with(monkeypatch, slither_path="/usr/bin/slither",
                         installed=["0.8.20"]) is True


def test_which_solc_alone_is_not_the_gate(monkeypatch):
    """🔴 이 단언이 원래 내가 쓰려던 오답을 잡는다.

    `shutil.which("solc")` 는 프로덕션에서 **항상 참**이다(solc-select shim).
    위 헬퍼는 solc 경로를 늘 돌려주므로, 이 테스트가 통과한다는 것은 판정이
    shim 이 아니라 **설치된 버전**을 보고 있다는 뜻이다.
    """
    assert _enabled_with(monkeypatch, slither_path="/usr/bin/slither", installed=[]) is False


def test_still_disabled_when_slither_binary_is_absent(monkeypatch):
    """기존 계약 유지 — slither 자체가 없으면 당연히 꺼진다."""
    assert _enabled_with(monkeypatch, slither_path=None, installed=["0.8.20"]) is False


def test_falls_back_to_which_when_solc_select_is_absent(monkeypatch):
    """solc-select 가 없는 환경(네이티브 solc)에서는 `which` 로 떨어진다."""
    import builtins
    monkeypatch.setattr("src.analyzer.io.tools.slither.shutil.which",
                        lambda name: f"/usr/bin/{name}")
    real_import = builtins.__import__

    def _no_solc_select(name, *a, **k):
        if name.startswith("solc_select"):
            raise ImportError("no solc_select")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _no_solc_select)
    assert _SlitherAnalyzer().is_enabled(_ctx()) is True
