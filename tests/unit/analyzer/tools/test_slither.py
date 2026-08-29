"""_SlitherAnalyzer 단위 테스트 — JSON 파싱 + subprocess mock (Phase D.2)."""
from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test_secret")
os.environ.setdefault("GITHUB_TOKEN", "ghp_test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123:ABC")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123")

import subprocess  # noqa: E402
import importlib.util  # noqa: E402
import sys  # noqa: E402
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


# ── pragma 사전 점검: 핀된 컴파일러가 못 맞추는 계약은 **벽이 아니라 skip** (#1568 B) ──
#
# `railway.toml` 은 solc **0.8.20 하나만** 핀한다. 그 컴파일러가 만족하지 못하는 pragma 를
# 가진 `.sol` 은 slither 가 **빈 stdout** 을 내고, #1564 가 그것을 미분석으로 올리므로
# 모든 Solidity PR 이 `incomplete` 로 막힌다 — 리뷰 대상 코드의 결함이 아니라 **환경 핀**이
# 만든 벽이다.
#
# 🔴 빈 stdout 은 구문 오류·크래시와 구별되지 않으므로 사후 판정이 불가능하다.
#    실행 **전에** pragma 와 설치된 컴파일러를 대조해야 한다.
#
# 실측(semantic_version NpmSpec, 설치 0.8.20):
#     ^0.8.0 True · >=0.7.0 <0.9.0 True · 0.8.20 True · >=0.4.22 True
#     ^0.4.24 False · ^0.6.0 False · 0.8.19 False · >=0.5.0 <0.6.0 False
#
# 🔴 `packaging` 은 쓸 수 없다 — `SpecifierSet("^0.8.0")` 이 `InvalidSpecifier` 다(실측).
# 🔴 crytic-compile 의 pragma 정규식도 재사용하지 않는다 — 그것은 범위 판정이 아니라
#    **정확 버전 추측**이라 `>=0.7.0 <0.9.0` 의 상한을 버린다(실측).

_INSTALLED_0820 = ["0.8.20"]

# 🔴 이 절은 `semantic_version` 을 **실제로** 쓴다. 없으면 판정이 폴백(True)을 타므로
#    테스트가 「틀린 이유로」 초록/빨강이 된다. 가짜 모듈을 끼우면 NpmSpec 의미론이 아니라
#    내 가짜를 재게 되므로, 부재 시에는 건너뛴다.
#    CI 는 Python 3.12 + semgrep(전이 의존 semantic-version~=2.10.0)이라 여기서 돈다 — 실측.
#    로컬 3.14 에는 semgrep 이 없어 건너뛴다.
# This block exercises real NpmSpec semantics; a fake module would measure the fake.
pytestmark_semver = pytest.mark.skipif(
    importlib.util.find_spec("semantic_version") is None,
    reason="semantic_version 부재 — pragma 판정이 폴백을 타 측정 불가(CI 3.12 에서 실행)",
)


def _enabled_with_pragma(monkeypatch, content: str, installed=None):
    """`is_enabled` 를 pragma·설치버전만 바꿔 태운다 — 네트워크를 타지 않는다."""
    import sys as _sys
    import types
    monkeypatch.setattr("src.analyzer.io.tools.slither.shutil.which",
                        lambda name: f"/usr/bin/{name}")
    mod = types.ModuleType("solc_select.solc_select")
    mod.installed_versions = lambda: (_INSTALLED_0820 if installed is None else installed)
    monkeypatch.setitem(_sys.modules, "solc_select", types.ModuleType("solc_select"))
    monkeypatch.setitem(_sys.modules, "solc_select.solc_select", mod)
    ctx = AnalyzeContext(filename="V.sol", content=content, language="solidity",
                         is_test=False, tmp_path="/tmp/V.sol")  # nosec B108
    return _SlitherAnalyzer().is_enabled(ctx)


@pytestmark_semver
@pytest.mark.parametrize("pragma", ["^0.4.24", "^0.6.0", "0.8.19", ">=0.5.0 <0.6.0"])
def test_unsatisfiable_pragma_skips_instead_of_walling(monkeypatch, pragma):
    """🔴 핀된 컴파일러가 못 맞추면 실행하지 않는다 — 실행하면 빈 stdout 이 벽이 된다."""
    src = f"// SPDX-License-Identifier: MIT\npragma solidity {pragma};\ncontract V {{}}\n"
    assert _enabled_with_pragma(monkeypatch, src) is False


@pytest.mark.parametrize("pragma", ["^0.8.0", ">=0.7.0 <0.9.0", "0.8.20", ">=0.4.22"])
def test_satisfiable_pragma_still_runs(monkeypatch, pragma):
    """🔴 부정 통제 — 맞출 수 있으면 그대로 돈다. 과차단하면 Solidity 분석이 사라진다."""
    src = f"// SPDX-License-Identifier: MIT\npragma solidity {pragma};\ncontract V {{}}\n"
    assert _enabled_with_pragma(monkeypatch, src) is True


def test_missing_pragma_still_runs(monkeypatch):
    """🔴 pragma 가 없으면 판단할 근거가 없다 — 막지 않는다(기존 동작 유지)."""
    assert _enabled_with_pragma(monkeypatch, "contract V {}\n") is True


def test_unparsable_pragma_still_runs(monkeypatch):
    """🔴 파싱 실패는 「못 맞춘다」가 아니다 — 실행하고 결과로 판정한다."""
    src = "pragma solidity 이건범위가아니다;\ncontract V {}\n"
    assert _enabled_with_pragma(monkeypatch, src) is True


@pytestmark_semver
def test_a_bare_version_number_in_a_comment_is_not_a_pragma(monkeypatch):
    """🔴 주석 안의 **맨 버전 숫자**가 판정을 바꾸면 안 된다.

    🔴 이 시험은 이름이 주장하던 것보다 좁다 — `_PRAGMA_RE` 는 `pragma solidity` 라는
    **선언문 형태**를 찾으므로 맨 숫자는 애초에 후보가 아니다. 어떤 구현으로도 통과한다.
    주석 인지 자체는 아래 `test_a_block_comment_pragma_does_not_mask_the_real_one` 이 잰다.
    A bare version number was never a candidate for this regex; this case is a weak control.
    """
    src = ("// 이 계약은 예전에 0.8.20 으로 빌드했다\n"
           "pragma solidity ^0.4.24;\ncontract V {}\n")
    assert _enabled_with_pragma(monkeypatch, src) is False


# ── 주석 안의 pragma 는 pragma 가 아니다 ─────────────────────────────────────
#
# 🔴 `_PRAGMA_RE` 는 주석 문법을 모르고 `search()` 는 **첫 매치**만 본다. `*` 접두가 없는
#    `/* … */` 블록이 실물 pragma 보다 앞에 있고 그 안의 한 줄이 `pragma solidity …;` 로
#    시작하면 그 줄이 판정을 가로챈다. 정규식 위 주석은 정반대를 선언하고 있었다.
#
# 🔴 양방향으로 잰다 — 한쪽만 재면 둘 중 하나만 고쳐도 초록이 된다.
#      가림    : 주석이 못 맞춤 · 실물이 맞춤 → 돌아야 하는데 안 돈다
#      역방향  : 주석이 맞춤 · 실물이 못 맞춤 → 못 맞추는 컴파일러로 돌아 빈 stdout → 벽
#
# Both directions: a comment must not mask a satisfiable pragma, nor enable an unsatisfiable one.


@pytestmark_semver
def test_a_block_comment_pragma_does_not_mask_the_real_one(monkeypatch):
    """🔴 가림 방향 — 실물 pragma 가 맞출 수 있으면 돈다."""
    src = ("/*\n"
           "pragma solidity ^0.4.24;\n"
           "*/\n"
           "// SPDX-License-Identifier: MIT\n"
           "pragma solidity ^0.8.0;\n"
           "contract V {}\n")
    assert _enabled_with_pragma(monkeypatch, src) is True


@pytestmark_semver
def test_a_block_comment_pragma_does_not_enable_an_unsatisfiable_contract(monkeypatch):
    """🔴 역방향 — 주석이 맞춰도 실물이 못 맞추면 돌지 않는다.

    돌면 slither 가 맞지 않는 컴파일러로 실행돼 빈 stdout 을 내고, `run()` 이 그것을
    미분석으로 올려 그 파일이 통째로 `incomplete` 가 된다 — #1571 이 없앤 벽이다.
    """
    src = ("/*\n"
           "pragma solidity ^0.8.0;\n"
           "*/\n"
           "pragma solidity ^0.4.24;\n"
           "contract V {}\n")
    assert _enabled_with_pragma(monkeypatch, src) is False


@pytestmark_semver
def test_a_trailing_block_comment_does_not_win(monkeypatch):
    """🔴 실물 pragma 뒤에 오는 블록주석이 판정을 뒤집지 않는다.

    🔴 이 시험은 「마지막 매치를 쓴다」는 오답을 **잡지 못한다**(실측: 그 뮤턴트에서 GREEN).
    주석을 먼저 지우므로 남는 pragma 가 하나뿐이라 첫 매치와 마지막 매치가 같아진다.
    실물 pragma 가 여럿인 파일(flatten 된 계약)에서만 둘이 갈리는데, 그때 무엇이 옳은지는
    이 PR 이 정하지 않았다.
    Does not discriminate the take-LAST variant: after stripping there is only one pragma left.
    """
    src = ("pragma solidity ^0.8.0;\n"
           "contract V {}\n"
           "/*\n"
           "pragma solidity ^0.4.24;\n"
           "*/\n")
    assert _enabled_with_pragma(monkeypatch, src) is True


@pytestmark_semver
@pytest.mark.parametrize("comment", [
    "/* pragma solidity ^0.4.24; */",
    " * pragma solidity ^0.4.24;",
    "// pragma solidity ^0.4.24;",
])
def test_comment_shapes_that_already_missed_keep_missing(monkeypatch, comment):
    """🔴 부정 통제 — 원래도 안 걸리던 형태가 수정 뒤에도 안 걸린다."""
    src = comment + "\npragma solidity ^0.8.0;\ncontract V {}\n"
    assert _enabled_with_pragma(monkeypatch, src) is True


@pytestmark_semver
def test_a_second_block_comment_does_not_swallow_the_real_pragma(monkeypatch):
    """🔴 탐욕 매칭 오답을 잡는다 — `.*?` 를 `.*` 로 바꾸면 두 주석 사이가 통째로 사라진다.

    그러면 실물 pragma 가 지워져 「pragma 없음」이 되고, 못 맞추는 계약이 조용히 돈다.
    Guards the greedy-regex wrong fix: it would delete everything between two block comments,
    erasing the real pragma and silently enabling an unsatisfiable contract.
    """
    src = ("/* 머리말 */\n"
           "pragma solidity ^0.4.24;\n"
           "/* 꼬리말 */\n"
           "contract V {}\n")
    assert _enabled_with_pragma(monkeypatch, src) is False


@pytestmark_semver
def test_an_unterminated_block_comment_does_not_decide(monkeypatch):
    """🔴 미종결 `/*` 뒤는 전부 주석이다 — 컴파일러가 그렇게 읽는다.

    그 안의 pragma 로 판정하면 「못 맞춘다」가 되어 분석을 잃는다. 판단 근거가 없는 것이
    맞으므로 막지 않고 설치본으로 돈다.
    Everything after an unterminated `/*` is comment; a pragma inside it must not decide.
    """
    src = ("/*\n"
           "pragma solidity ^0.4.24;\n"
           "contract V {}\n")
    assert _enabled_with_pragma(monkeypatch, src) is True


def test_no_installed_compiler_is_still_the_procurement_gate(monkeypatch):
    """기존 계약 유지 — 아티팩트가 0건이면 pragma 와 무관하게 꺼진다(#1567)."""
    src = "pragma solidity ^0.8.0;\ncontract V {}\n"
    assert _enabled_with_pragma(monkeypatch, src, installed=[]) is False


# ── 고른 컴파일러를 slither 에 실제로 넘긴다 (#1568 A — 형태 변경) ──────────────
#
# 🔴 원안(`is_enabled` 를 `current_version()` 으로 게이트)은 **틀렸다.** 두 가지 이유로:
#    (1) 아티팩트가 디스크에 있으면 컴파일러는 **돌 수 있다** — 전역 핀이 없다고 건너뛰는 것은
#        있는 관측면을 버리는 것이다.
#    (2) `current_version()` 은 `argparse.ArgumentTypeError` 를 낸다. 그것은 `ImportError`·
#        `OSError` 가 아니고 `is_enabled` 는 `_run_analyzers` 의 `try` **바깥**이라 예외가
#        `analyze_file` 밖으로 샌다 → `pipeline.py` 가 파일 단위로 삼켜 빈 결과를 만든다.
#        혼합 PR 이면 미분석 Solidity 가 **깨끗함**으로 채점된다 — 지금의 벽보다 나쁘다.
#
# 실측(상태 U = 아티팩트 있음 · global-version 없음, slither 0.11.5):
#     기본 호출                       exit=1   · stdout **0자**   ← 벽
#     --solc-solcs-select 0.8.36     exit=127 · stdout 16069자 · success:true
#
# #1571 이 이미 「어느 설치본이 pragma 를 만족하는가」를 고른다. 그 값을 **넘기기만** 하면
# 전역 핀에 의존하지 않게 되고, 조달을 넓혔을 때 추가 컴파일러가 놀지 않는다.


@pytestmark_semver
def test_matched_version_is_passed_to_slither(monkeypatch):
    """🔴 고른 컴파일러를 argv 로 넘긴다 — 전역 핀이 없어도 돈다."""
    import types
    captured = {}

    def _fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return MagicMock(stdout='{"success": true, "results": {"detectors": []}}',
                         stderr="", returncode=0)

    mod = types.ModuleType("solc_select.solc_select")
    mod.installed_versions = lambda: ["0.7.6", "0.8.20"]
    monkeypatch.setitem(sys.modules, "solc_select", types.ModuleType("solc_select"))
    monkeypatch.setitem(sys.modules, "solc_select.solc_select", mod)
    monkeypatch.setattr("src.analyzer.io.tools.slither.subprocess.run", _fake_run)

    ctx = AnalyzeContext(filename="V.sol", content="pragma solidity ^0.8.0;\ncontract V {}",
                         language="solidity", is_test=False, tmp_path="/tmp/V.sol")  # nosec B108
    _SlitherAnalyzer().run(ctx)
    cmd = captured["cmd"]
    assert "--solc-solcs-select" in cmd, f"고른 버전을 안 넘긴다: {cmd}"
    assert cmd[cmd.index("--solc-solcs-select") + 1] == "0.8.20", (
        f"pragma ^0.8.0 인데 0.8.20 이 아닌 것을 넘겼다: {cmd}"
    )


def test_no_flag_when_no_version_matches(monkeypatch):
    """🔴 부정 통제 — 고를 수 없으면 플래그를 붙이지 않는다(기존 호출 형태 유지).

    이 경로는 `is_enabled` 가 이미 막지만, `run()` 이 단독으로도 안전해야 한다.
    """
    import types
    captured = {}
    monkeypatch.setattr("src.analyzer.io.tools.slither.subprocess.run",
                        lambda cmd, *a, **k: (captured.update(cmd=cmd),
                                              MagicMock(stdout='{"success": true, "results": {}}',
                                                        stderr="", returncode=0))[1])
    mod = types.ModuleType("solc_select.solc_select")
    mod.installed_versions = lambda: []
    monkeypatch.setitem(sys.modules, "solc_select", types.ModuleType("solc_select"))
    monkeypatch.setitem(sys.modules, "solc_select.solc_select", mod)

    ctx = AnalyzeContext(filename="V.sol", content="contract V {}", language="solidity",
                         is_test=False, tmp_path="/tmp/V.sol")  # nosec B108
    _SlitherAnalyzer().run(ctx)
    assert "--solc-solcs-select" not in captured["cmd"]
