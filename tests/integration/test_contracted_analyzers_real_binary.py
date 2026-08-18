"""조달 계약 3종 실바이너리 통합 — rubocop · golangci-lint · slither (#1444).

## 왜 (2026-08-18 실측)

셋 다 단위 테스트가 **전량 mock** 이고 `tests/integration/` 에 실바이너리 테스트가 0건이었다.
원인은 「테스트를 안 썼다」가 아니라 **CI 가 그 도구를 설치하지 않았다**는 것이다 —
계약 16종 중 CI 조달은 10종뿐이었다. 조달되지 않으니 쓸 수가 없었다.

계약의 뜻은 「이 도구가 사라지면 배포 회귀다」이고, 부재 시 `static.py` 가 `incomplete` 로
승격해 auto-merge 를 막는다. 그런데 **그 도구가 실제로 이슈를 내는지**는 아무도 확인한 적이 없다.
이 파일이 그 축이다.

## 🔴 부재 시 `skip` 하지 않고 **loud** 하게 실패한다

`skipif` 는 「안 쟀음」을 초록으로 보이게 한다 — 이 리포가 반복해 온 fail-open 이다.
CI 는 조달 계약 전량을 설치하므로(`ci.yml` §Install contracted analyzers) 여기서 부재는
**조달 회귀**이지 환경 차이가 아니다.

로컬(Windows 등)에서는 `CONTRACTED_ANALYZER_TESTS=optional` 로 명시 완화할 수 있다 —
그 경우에도 조용히 통과하지 않고 「안 쟀음」을 인쇄한다.
Absence is a procurement regression in CI, not an environment difference: fail loudly.
"""
import os
import shutil
import subprocess  # nosec B404 — 로컬 분석기 실행
import sys
import textwrap

import pytest

_OPTIONAL = os.environ.get("CONTRACTED_ANALYZER_TESTS", "").lower() == "optional"


def _not_measured(reason: str) -> None:
    """「안 쟀음」을 **인쇄하고** skip — 조용한 초록을 만들지 않는다."""
    print(f"\nℹ️ 안 쟀음 (단언 0건) — {reason}", file=sys.stderr)
    pytest.skip(reason)


def _require(tool: str) -> None:
    """도구가 없으면 **실패**한다 — 부재는 조달 회귀이지 환경 차이가 아니다.

    CI 는 조달 계약 전량을 설치한다(`ci.yml` §Install contracted analyzers).
    로컬에서 건너뛰려면 `CONTRACTED_ANALYZER_TESTS=optional` 을 **명시**한다.
    """
    if shutil.which(tool):
        return
    if _OPTIONAL:
        _not_measured(f"`{tool}` 부재 · 완화 모드(CONTRACTED_ANALYZER_TESTS=optional)")
    pytest.fail(
        f"🔴 조달 계약 도구 `{tool}` 이 없다. 계약(`PROVISIONED_ANALYZERS`)에 있는 도구는\n"
        f"   CI 가 설치한다(`ci.yml` §Install contracted analyzers) — 부재는 조달 회귀다.\n"
        f"   로컬에서 건너뛰려면 CONTRACTED_ANALYZER_TESTS=optional 을 명시할 것."
    )


def _run(cmd: list[str], cwd) -> subprocess.CompletedProcess:
    """분석기 실행 — 🔴 Windows 의 shim 실행 불가만 「안 쟀음」으로 좁혀 완화한다.

    `rubocop` 같은 ruby/`.cmd` shim 은 `which` 로는 찾히는데 `CreateProcess` 가 직접
    실행하지 못한다(`FileNotFoundError`). 그것은 **플랫폼 한계**이지 조달 회귀가 아니다 —
    `test_eslint_analyzer.py` 가 같은 이유로 Windows 를 제외한다. CI(Linux)가 이 축을 담당한다.
    🔴 그런데 **실행 가능한 것까지 미리 제외하지는 않는다** — 실제로 실패할 때만 완화한다
    (실측: `slither` 는 이 머신에서 정상 실행된다).
    Narrow the Windows relaxation to actual shim-exec failures, not a blanket platform skip.
    """
    try:
        return subprocess.run(  # nosec B603
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(cwd), timeout=180, check=False,
        )
    except OSError as exc:
        if os.name == "nt":
            _not_measured(f"Windows 가 `{cmd[0]}` shim 을 직접 실행 못 함 ({exc.__class__.__name__}) · CI=Linux 담당")
        raise

def test_rubocop_emits_a_rule_id_on_a_dirty_ruby_file(tmp_path):
    """실 rubocop 이 위반을 잡고 **ruleId(cop 이름)** 를 낸다."""
    _require("rubocop")
    src = tmp_path / "dirty.rb"
    # 문자열 리터럴 스타일 + 미사용 변수 — 기본 룰셋이 잡는다.
    src.write_text('x = "unused"\nputs  1\n', encoding="utf-8")
    proc = _run(["rubocop", "--format", "json", str(src)], tmp_path)
    assert proc.stdout.strip(), f"rubocop 이 출력을 내지 않았다: {proc.stderr[-300:]}"
    assert '"cop_name"' in proc.stdout, (
        f"cop_name(ruleId)이 없다 — 분석기가 룰을 적용하지 않았다: {proc.stdout[:300]}"
    )


def test_golangci_lint_runs_and_reports_structurally(tmp_path):
    """실 golangci-lint 가 Go 파일을 분석하고 **구조화 출력**을 낸다."""
    _require("golangci-lint")
    (tmp_path / "go.mod").write_text("module x\n\ngo 1.21\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(textwrap.dedent("""
        package main

        import "fmt"

        func main() {
            unused := 1
            fmt.Println("hi")
        }
    """).lstrip(), encoding="utf-8")
    proc = _run(["golangci-lint", "run", "--out-format", "json", "./..."], tmp_path)
    out = proc.stdout.strip()
    assert out.startswith("{"), (
        f"JSON 출력이 아니다 — 분석기가 돌지 않았다.\nstdout={out[:200]}\nstderr={proc.stderr[-300:]}"
    )
    assert '"Issues"' in out, f"Issues 키가 없다: {out[:200]}"


def test_slither_has_a_solc_and_parses_a_contract(tmp_path):
    """실 slither 가 solc 를 찾아 Solidity 를 **파싱**한다.

    🔴 slither 는 pip 로 오지만 `solc` 없이는 아무것도 못 한다 — 「설치됨」과 「동작함」이
    갈리는 지점이라 이 축이 필요하다.
    """
    _require("slither")
    _require("solc")
    src = tmp_path / "C.sol"
    src.write_text(textwrap.dedent("""
        // SPDX-License-Identifier: MIT
        pragma solidity ^0.8.20;

        contract C {
            uint256 public x;
            function set(uint256 v) public { x = v; }
        }
    """).lstrip(), encoding="utf-8")
    proc = _run(["slither", str(src), "--json", "-"], tmp_path)
    combined = proc.stdout + proc.stderr
    assert "Error" not in proc.stderr or "compilation" not in proc.stderr.lower(), (
        f"solc 컴파일 실패 — solc 조달을 확인할 것: {proc.stderr[-300:]}"
    )
    assert '"success"' in proc.stdout or "Compilation warnings" in combined or proc.returncode in (0, 255), (
        f"slither 가 계약을 파싱하지 못했다: {combined[-400:]}"
    )
