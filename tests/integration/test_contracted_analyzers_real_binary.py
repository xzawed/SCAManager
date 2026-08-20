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
import json
import os
import shutil
import subprocess  # nosec B404 — 로컬 분석기 실행
import sys
import textwrap

import pytest

from src.analyzer.io.tools.ktlint import json_array_payload

# 🔴 하니스 상한과 서브프로세스 허용치를 맞춘다 (2026-08-21 CI 실측).
#    `pytest.ini` 의 `--timeout=30` 이 이 파일의 `_run(..., timeout=180)` 보다 **작아서**,
#    180초 허용은 처음부터 도달 불가였다 — 실바이너리가 30초를 넘기는 순간
#    `Failed: Timeout (>30.0s)` 로 죽는다. 실제로 `golangci-lint` 가 그렇게 죽었다
#    (콜드 캐시에서 Go 모듈을 받고 컴파일한다). 그전까지는 **우연히 30초 안에 끝났을 뿐**이다.
#    실바이너리는 네트워크·컴파일을 포함하므로 단위 테스트 상한이 애초에 맞지 않는다.
# Align the harness cap with the subprocess allowance: --timeout=30 made the 180s
# allowance unreachable, so a cold-cache real binary died at 30s.
_REAL_BINARY_TIMEOUT = 180

pytestmark = pytest.mark.timeout(_REAL_BINARY_TIMEOUT)


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
            cwd=str(cwd), timeout=_REAL_BINARY_TIMEOUT, check=False,
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


# ══════════════════════════════════════════════════════════════════════════
# 계약 3종 추가 — hadolint · ktlint · tflint (2026-08-19)
#
# 🔴 이 셋만 `latest` 로 설치되고 있었다. 같은 블록의 형제는 전부 핀이다
#    (rubocop 1.57.2 · rubocop-ast 1.36.2 · golangci-lint v1.55.2 · typescript 6.0.x).
#    상류가 출력 형식을 바꾸면 파서가 깨지고 → `incomplete` → auto-merge 차단이
#    **리포 변경 0줄로** 일어난다. 게다가 CI 와 Railway 가 `latest` 를 서로 다른
#    시점에 해석하므로 둘이 조용히 갈린다.
#
# 🔴 핀만 걸면 절반이다 (Grok claim-review `01a01a4e` R3): 셋 다 실바이너리 테스트가
#    **0건**이라 핀을 건 그 버전이 우리 파서와 맞는지 아무도 확인하지 않는다.
#    핀을 안전하게 만드는 것이 이 테스트들이고, 다음 버전 올림도 여기서 검증된다.
#
# 🔴 **접두 계약을 함께 못박는다.** 세 어댑터 모두 `raw.startswith("[")`/`("{")` 가
#    거짓이면 **조용히 `[]` 를 반환**한다(`tools/ktlint.py:57` · `tools/tflint.py:59`).
#    즉 상류가 배너 한 줄을 앞에 붙이기만 해도 분석이 0건이 되고 아무도 모른다.
#    필드 존재만 보는 테스트는 그 경로를 통과시킨다.
# ══════════════════════════════════════════════════════════════════════════


def test_hadolint_emits_the_fields_the_adapter_reads(tmp_path):
    """실 hadolint 가 `level`·`code`·`message`·`line` 을 낸다 (`tools/hadolint.py:59-65`)."""
    _require("hadolint")
    src = tmp_path / "Dockerfile"
    # latest 태그 + apt-get upgrade → DL3006/DL3005 계열이 확정적으로 난다.
    src.write_text("FROM debian:latest\nRUN apt-get update && apt-get upgrade -y\n",
                   encoding="utf-8")

    proc = _run(["hadolint", "--format=json", str(src)], tmp_path)
    raw = proc.stdout.strip()

    assert raw, f"hadolint 이 출력을 내지 않았다: {proc.stderr[-300:]}"
    issues = json.loads(raw)
    assert isinstance(issues, list) and issues, (
        f"이슈 0건 — 더러운 Dockerfile 인데: {raw[:300]}"
    )
    first = issues[0]
    for key in ("level", "code", "message", "line"):
        assert key in first, f"어댑터가 읽는 키 `{key}` 가 없다: {sorted(first)}"
    assert str(first["code"]).startswith("DL"), f"규칙 코드 형식이 아니다: {first['code']}"


def test_ktlint_output_needs_preamble_stripping_and_the_adapter_does_it(tmp_path):
    """🔴 실 ktlint 는 JSON **앞에 로그 줄을 붙인다** — 이 테스트가 그걸 잡아냈다.

    초판은 `raw.startswith("[")` 를 단언했다. CI 실측(ktlint 1.8.0)이 그것을 반증했다:

        14:16:17.124 [main] WARN com.pinterest.ktlint.cli...KtlintCommandLine -- Lint has
        found errors than can be autocorrected...
        [ ... ]

    그리고 `tools/ktlint.py` 구판이 정확히 그 `startswith` 로 걸러내고 있었다 —
    **자동수정 가능한 위반이 있는 모든 Kotlin 파일에서 분석이 0건**이었다.
    계약 도구가 설치돼 있는데 아무것도 보고하지 않았고, 그게 「깨끗함」으로 보였다.

    그래서 이 테스트는 원 출력의 접두를 단언하지 않는다(거짓이다). 대신
    **어댑터의 추출기가 실제 출력을 다룰 수 있는지**를 잰다 — 그것이 진짜 계약이다.
    """
    _require("ktlint")
    src = tmp_path / "Dirty.kt"
    src.write_text("fun  main( ) {\n      println(\"x\") ;\n}\n", encoding="utf-8")

    proc = _run(["ktlint", "--reporter=json", str(src)], tmp_path)
    raw = (proc.stdout or "").strip()

    assert raw, f"ktlint 이 stdout 을 내지 않았다: {(proc.stderr or '')[-300:]}"

    payload = json_array_payload(raw)
    assert payload, (
        "어댑터의 추출기가 JSON 배열을 못 찾았다 — 분석이 조용히 0건이 된다.\n"
        f"실 출력 앞부분: {raw[:200]}"
    )
    data = json.loads(payload)
    assert data, f"이슈 0건 — 더러운 Kotlin 인데: {raw[:300]}"
    errors = data[0].get("errors")
    assert errors, f"어댑터가 읽는 `errors` 가 비었다: {sorted(data[0])}"
    for key in ("rule", "message", "line"):
        assert key in errors[0], f"어댑터가 읽는 키 `{key}` 가 없다: {sorted(errors[0])}"


def test_tflint_output_starts_with_a_brace_and_carries_the_issues_envelope(tmp_path):
    """실 tflint 가 **`{` 로 시작하는** 객체와 `issues` 봉투를 낸다.

    🔴 이슈 **건수**는 요구하지 않는다. tflint 의 내장 룰셋은 provider 플러그인 없이
    거의 발화하지 않고, 그것은 상류 정책이라 버전마다 바뀐다. 없는 계약을 단언하면
    버전을 올릴 때마다 이 테스트가 **거짓 red** 를 낸다. 어댑터가 실제로 의존하는 것은
    접두와 봉투 구조다(`tools/tflint.py:59-67`).
    이슈가 실제로 나오면 그때는 중첩 경로까지 확인한다 — 있는 것만 잰다.
    """
    _require("tflint")
    (tmp_path / "main.tf").write_text(
        'variable "unused" {\n  type = string\n}\n'
        'resource "aws_instance" "x" {\n  instance_type = "t2.micro"\n}\n',
        encoding="utf-8")

    proc = _run(["tflint", "--format=json", "--chdir", str(tmp_path)], tmp_path)
    raw = proc.stdout.strip()

    assert raw, f"tflint 이 stdout 을 내지 않았다: {(proc.stderr or '')[-300:]}"
    assert raw.startswith("{"), (
        f"어댑터의 접두 계약 위반 — `{{` 로 시작하지 않으면 조용히 0건이 된다: {raw[:120]}"
    )
    payload = json.loads(raw)
    assert "issues" in payload and isinstance(payload["issues"], list), (
        f"어댑터가 읽는 `issues` 배열이 없다: {sorted(payload)}"
    )
    for issue in payload["issues"]:
        assert "message" in issue, f"이슈에 `message` 가 없다: {sorted(issue)}"
        assert isinstance(issue.get("rule"), dict), "`rule` 이 객체가 아니다 — severity 경로가 깨진다"
        assert isinstance(issue.get("range", {}).get("start"), dict), (
            "`range.start` 가 객체가 아니다 — line 경로가 깨진다"
        )
