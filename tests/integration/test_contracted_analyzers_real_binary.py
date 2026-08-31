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
from src.analyzer.io.tools.sqlfluff import _SqlfluffAnalyzer
from src.analyzer.pure.registry import AnalyzeContext

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


def test_sqlfluff_emits_a_document_even_when_clean_and_uses_start_line_no(tmp_path):
    """🔴 실 sqlfluff 는 (a) 깨끗해도 JSON 문서를 내고 (b) `start_line_no` 를 쓴다.

    (a) 때문에 「빈 출력 = 깨끗함」이 틀렸다 — 빈 출력은 분석이 시작조차 못 한 것이다.
    (b) 때문에 `line_no` 만 읽으면 실물에서는 **모든 이슈의 line 이 0** 이 된다
        (sqlfluff 3.0 의 키 rename, 핀은 4.3.0).

    mock 은 이 둘을 원리적으로 못 잡는다 — 픽스처의 키와 빈값 여부를 **쓰는 사람이**
    정하기 때문이다. 실제로 단위 테스트 픽스처가 `line_no` 를 써서 어긋남을 가리고 있었다.
    A mock cannot catch either: the fixture author picks the key and the emptiness.
    """
    _require("sqlfluff")
    clean = tmp_path / "clean.sql"
    clean.write_text("SELECT 1;\n", encoding="utf-8")

    proc = _run(["sqlfluff", "lint", "--format=json", "--dialect=ansi", str(clean)], tmp_path)
    raw = proc.stdout.strip()
    assert raw.startswith("["), (
        f"깨끗한 실행도 JSON 배열을 내야 한다 — 「빈 출력 = 깨끗함」 가정의 근거가 사라진다: "
        f"exit={proc.returncode} stdout={raw[:200]!r} stderr={(proc.stderr or '')[-200:]!r}"
    )

    dirty = tmp_path / "dirty.sql"
    dirty.write_text("select  a,b   from t where  x=1\n", encoding="utf-8")
    proc = _run(["sqlfluff", "lint", "--format=json", "--dialect=ansi", str(dirty)], tmp_path)
    payload = json.loads(proc.stdout.strip())
    violations = [v for f in payload for v in f.get("violations", [])]
    assert violations, f"더러운 SQL 인데 위반 0건: {proc.stdout[:300]}"
    assert any("start_line_no" in v or "line_no" in v for v in violations), (
        f"어댑터가 읽는 줄번호 키가 둘 다 없다: {sorted(violations[0])}"
    )


def test_sqlfluff_adapter_reports_a_real_line_number(tmp_path):
    """어댑터가 실 출력에서 **0 이 아닌 줄번호**를 뽑아낸다.

    `line_no` 만 읽던 동안 이 단언은 실물에서 전건 0 이었다(mock 은 초록이었다).
    """
    _require("sqlfluff")
    src = tmp_path / "dirty.sql"
    src.write_text("select  a,b   from t where  x=1\n", encoding="utf-8")
    ctx = AnalyzeContext(filename="dirty.sql", content="", language="sql",
                         is_test=False, tmp_path=str(src))
    try:
        issues = _SqlfluffAnalyzer().run(ctx)
    except OSError as exc:  # Windows shim 실행 불가만 완화 — `_run` 과 같은 규칙
        if os.name == "nt":
            _not_measured(f"Windows 가 sqlfluff shim 을 직접 실행 못 함 ({exc.__class__.__name__})")
        raise
    assert issues, "더러운 SQL 인데 어댑터가 이슈 0건을 냈다"
    assert all(i.line > 0 for i in issues), (
        f"줄번호가 0 이다 — 키 이름이 어긋났다: {[(i.line, i.message[:40]) for i in issues[:3]]}"
    )


def test_sqlfluff_crash_raises_instead_of_reporting_a_clean_file(tmp_path):
    """🔴 sqlfluff 가 분석하지 못하면 어댑터는 **raise** 한다 — `[]` 가 아니다.

    `sql` 은 provisioned 분석기가 sqlfluff 하나뿐인 유일한 언어라(실측, #1521)
    여기서 `[]` 를 돌려주면 미분석 SQL 이 «이슈 0건 · 완전» 으로 기록되고
    정적 만점을 받은 채 auto-merge 된다 — 대체 관측면이 없다.
    """
    _require("sqlfluff")
    missing = tmp_path / "does_not_exist.sql"  # 실측: exit 2 · stdout 빈값
    ctx = AnalyzeContext(filename="does_not_exist.sql", content="", language="sql",
                         is_test=False, tmp_path=str(missing))
    try:
        with pytest.raises(RuntimeError, match="did not analyze"):
            _SqlfluffAnalyzer().run(ctx)
    except FileNotFoundError as exc:  # 바이너리 자체 부재는 이 테스트의 대상이 아니다
        if os.name == "nt":
            _not_measured(f"Windows 가 sqlfluff shim 을 직접 실행 못 함 ({exc.__class__.__name__})")
        raise


def test_sqlfluff_parse_failure_is_a_violation_not_a_crash(tmp_path):
    """🔴 과탐 방어 — 어댑터를 fail-closed 로 바꿔도 **정상 PR 을 막지 않는다**.

    어댑터는 `--dialect=ansi` 를 고정한다. 그러니 PostgreSQL·T-SQL 문법이나 아예
    파싱 불가한 텍스트가 들어오면 「분석 실패」로 올라가 auto-merge 가 막히는 것 아닌가 —
    이것이 fail-closed 전환의 유일한 실질 위험이다(가드의 자살).

    실측(sqlfluff 4.2.2)은 아니라고 답한다. sqlfluff 는 파싱 실패를 **JSON 안의 `PRS`
    위반으로 보고**하고 exit 1 로 끝낸다. 즉 stdout 은 여전히 JSON 배열이라 어댑터의
    판별식을 통과한다. raise 가 나는 것은 sqlfluff 가 **실행조차 못 한** 경우뿐이다.

    이 테스트가 red 가 되면 그 전제가 깨진 것이다 — 판별식을 바꾸기 전에 여기를 본다.
    Measured: sqlfluff reports parse failures as a PRS violation inside the JSON document,
    so hardening the adapter cannot turn ordinary SQL into a blocked merge.
    """
    _require("sqlfluff")
    probes = {
        "pg.sql": "SELECT a::text FROM t WHERE b @> ARRAY[1,2];\n",   # PostgreSQL 전용 문법
        "tsql.sql": "SELECT TOP 10 [a] FROM [dbo].[t];\n",            # T-SQL 전용 문법
        "garbage.sql": "this is not sql at all !!! ###\n",            # 파싱 불가
        "truncated.sql": "SELECT * FROM\n",                           # 절단
    }
    for name, sql in probes.items():
        src = tmp_path / name
        src.write_text(sql, encoding="utf-8")
        proc = _run(["sqlfluff", "lint", "--format=json", "--dialect=ansi", str(src)], tmp_path)
        raw = proc.stdout.strip()
        assert raw.startswith("["), (
            f"{name}: 파싱 실패가 비-JSON 으로 나왔다 — 어댑터가 raise 하게 되어 "
            f"정상 SQL PR 의 auto-merge 가 막힌다: exit={proc.returncode} {raw[:200]!r}"
        )

        ctx = AnalyzeContext(filename=name, content="", language="sql",
                             is_test=False, tmp_path=str(src))
        try:
            issues = _SqlfluffAnalyzer().run(ctx)   # raise 하면 이 줄에서 터진다
        except OSError as exc:
            if os.name == "nt":
                _not_measured(f"Windows 가 sqlfluff shim 을 직접 실행 못 함 ({exc.__class__.__name__})")
            raise
        assert isinstance(issues, list), f"{name}: 어댑터가 목록을 내지 않았다"


def test_sqlfluff_silently_skips_large_files_and_the_adapter_refuses_to_call_it_clean(tmp_path):
    """🔴 sqlfluff 는 큰 파일을 **분석하지 않고 건너뛴다** — 그리고 exit 0 으로 끝낸다.

    `large_file_skip_byte_limit` 기본값은 20,000 바이트다. 넘으면 stdout 이 `[]`(엔트리 0개)
    이고 종료코드는 **0** 이다. 어댑터가 그것을 「깨끗함」으로 읽으면 20KB 넘는 SQL 이
    전부 정적 만점을 받고 auto-merge 된다 — `sql` 은 대체 관측면이 없는 유일한 언어다.

    이 테스트는 **같은 내용을 길이만 바꿔** 두 번 돌린다. 내용이 같은데 판정이 갈리면
    그것은 파일이 깨끗해서가 아니라 **재지 않았기 때문**이다. CLI 플래그로는 끌 수 없어
    (`--large-file-skip-byte-limit` 는 존재하지 않는다) 어댑터가 raise 로 막는다.

    Measured: identical content at 3.2KB yields violations, at 32KB yields `[]` with exit 0.
    Same content, different verdict — that is not cleanliness, it is a skipped file.
    """
    _require("sqlfluff")
    line = "select  a,b   from t where  x=1\n"          # 확정적으로 위반을 낸다

    small = tmp_path / "small.sql"
    small.write_text(line * 100, encoding="utf-8")       # ~3.2KB — 한도 아래
    proc = _run(["sqlfluff", "lint", "--format=json", "--dialect=ansi", str(small)], tmp_path)
    small_entries = json.loads(proc.stdout.strip())
    assert small_entries and small_entries[0].get("violations"), (
        f"한도 아래인데 위반 0건 — 프로브가 더러운 SQL 이 아니게 됐다: {proc.stdout[:200]}"
    )

    big = tmp_path / "big.sql"
    big.write_text(line * 1000, encoding="utf-8")        # ~32KB — 한도 위
    assert big.stat().st_size > 20_000, "프로브가 한도를 넘지 못했다 — 이 테스트가 공허하다"
    proc = _run(["sqlfluff", "lint", "--format=json", "--dialect=ansi", str(big)], tmp_path)
    big_entries = json.loads(proc.stdout.strip())
    assert big_entries == [], (
        "sqlfluff 가 큰 파일을 더 이상 건너뛰지 않는다 — 기본 한도가 바뀌었거나 설정이 끼었다. "
        f"어댑터의 zero-entry 판정을 재검토하라: {proc.stdout[:200]}"
    )

    # 🔴 핵심 — 어댑터는 그 `[]` 를 «깨끗함» 으로 읽지 않는다.
    ctx = AnalyzeContext(filename="big.sql", content="", language="sql",
                         is_test=False, tmp_path=str(big))
    try:
        with pytest.raises(RuntimeError, match="did not analyze"):
            _SqlfluffAnalyzer().run(ctx)
    except FileNotFoundError as exc:
        if os.name == "nt":
            _not_measured(f"Windows 가 sqlfluff shim 을 직접 실행 못 함 ({exc.__class__.__name__})")
        raise


# ══════════════════════════════════════════════════════════════════════════════
# W2 크래시 판별식 실측 (#1557) — **측정 먼저, 전환은 그 다음**
# ══════════════════════════════════════════════════════════════════════════════
#
# 배포본에서 **실제로 도는** 잔여 fail-open 은 5개였고 ktlint 는 #1578·#1579 가 처리했다.
# 넷은 각각 자기 언어의 **유일한 조달 전담 관측면**이다(프로덕션 `supports()` ×
# `PROVISIONED_ANALYZERS` 실측):
#
#     cppcheck -> c · cpp      golangci-lint -> go
#     hadolint -> dockerfile   shellcheck    -> shell
#
# 🔴 그중 `cppcheck` · `hadolint` 는 **이미 전환됐다**(`_W2_CONVERTED` 참조). 남은 것은
#    `golangci-lint` · `shellcheck` 이고, 둘은 **크래시해도 파싱 가능한 출력을 낸다**(아래 표) —
#    stdout 만 보는 판별식이 원리적으로 불가능한 쪽이다.
#
# 전환 전에는 크래시가 `[]` 를 돌려주고, `static.py::            result.issues.extend(analyzer.run(ctx))`
# 다음 줄의 `ran += 1` 이 그것을 **정상 실행으로 센다**. 그래서 #1570 의
# `no_dedicated_observer` 축도 이 자리를 못 잡는다 — 결과는 「이슈 0건 · 완전」이다.
#
# 🔴 **왜 바로 전환하지 않는가.** #1564 가 rubocop 에서 배운 것: **크래시해도 유효 JSON 을
#    내는 도구가 있다.** 그러면 「파싱 불가 = 미분석」 판별식이 그 도구에서 조용히 빗나간다.
#    반대로 「빈 출력 = 미분석」으로 잡으면 깨끗한 파일이 통째로 차단된다(#1564 → #1567).
#    판별식은 **도구마다 실측해야** 하는데 이 개발 PC 에는 네 바이너리가 하나도 없다.
#    CI 는 넷 다 설치한다 — 그래서 여기가 계기다.
#
# 🔴 **이 절은 오늘의 fail-open 을 단언한다.** 크래시 행의 `[]` 는 **기록 중인 결함**이지
#    바라는 동작이 아니다. 어떤 도구를 fail-closed 로 돌리면 그 행이 red 가 되고, 그때
#    `pytest.raises` 로 바꾸면서 **어떤 판별식으로 잡았는지**를 여기 남긴다.
#
# Measure before converting: the crash discriminant differs per tool (rubocop emits valid JSON
# when it crashes), and none of these four binaries exist on the dev PC. CI is the instrument.


_W2_TOOLS = {
    # 등록명: (어댑터 모듈, 클래스, 언어, 확장자, 깨끗한 원본)
    "cppcheck": ("cppcheck", "_CppCheckAnalyzer", "cpp", ".cpp",
                 "int main() { return 0; }\n"),
    "golangci-lint": ("golangci_lint", "_GolangciLintAnalyzer", "go", ".go",
                      "package main\n\nfunc main() {}\n"),
    "hadolint": ("hadolint", "_HadolintAnalyzer", "dockerfile", "",
                 "FROM scratch\n"),
    "shellcheck": ("shellcheck", "_ShellCheckAnalyzer", "shell", ".sh",
                   "#!/bin/sh\necho hi\n"),
}

# 🔴 **이미 fail-closed 로 전환된 도구와 그 판별식.** 전환하면 이 표에 한 줄을 더한다 —
#    「어떤 판별식으로 잡았는지」가 여기 남아야 다음 사람이 근거 없이 흉내내지 않는다.
# Tools already converted, with the discriminant each one uses.
_W2_CONVERTED = {
    "cppcheck": "빈 stderr — 성공하면 항상 결과 XML 봉투를 낸다",
    "hadolint": "빈 stdout — 성공하면 항상 JSON 배열을 낸다(깨끗해도 `[]`)",
    "shellcheck": "읽어 낸 이슈 0건 + 비정상 종료 — 크래시 stdout 이 깨끗과 동일해 모양으로는 못 가른다",
}

_W2_DIRTY = {
    "cppcheck": "int main(){int *p=0;*p=1;return 0;}\n",
    "golangci-lint": "package main\n\nfunc main() { x := 1; _ = x }\n",
    "hadolint": "FROM ubuntu:latest\nRUN apt-get update\nADD x /x\n",
    "shellcheck": "#!/bin/sh\nrm -rf $1\necho $UNQUOTED\n",
}


def _w2_adapter(module_name: str, class_name: str):
    """어댑터를 string-path 로 가져온다 — 이 파일의 `from src… import` 와 이중 형태를 만들지 않는다."""
    import importlib  # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    module = importlib.import_module("src.analyzer.io.tools." + module_name)
    return getattr(module, class_name)()


def _w2_observe(adapter, ctx):
    """어댑터를 **프로덕션 경로로** 한 번 태우고, 그 안에서 실제로 돈 서브프로세스를 그대로 본다.

    🔴 argv 를 손으로 옮겨 적지 않는다 — 그러면 어댑터가 argv 를 바꾸는 순간 이 측정이
    조용히 다른 것을 재게 된다. `subprocess.run` 을 tee 해서 **어댑터가 실제로 부른 것**을 잡는다.
    Tee the real subprocess instead of re-typing argv, so the measurement cannot drift.
    """
    from unittest.mock import patch  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    seen = []
    real = subprocess.run

    def _tee(*args, **kwargs):
        proc = real(*args, **kwargs)
        seen.append(((args[0] if args else kwargs.get("args")), proc))
        return proc

    with patch("subprocess.run", _tee):
        try:
            return seen, adapter.run(ctx), None
        except Exception as exc:  # noqa: BLE001 — 무엇이 올라오는지가 측정 대상이다
            return seen, None, exc


def _w2_record(tool: str, case: str, seen, verdict, exc) -> str:
    """관측을 한 줄로 만들고 **경고로 띄운다** — pytest 경고 요약이 CI 로그에 남는다.

    통과한 테스트의 stdout 은 CI 로그에 나오지 않는다. 「쟀는데 안 보인다」를 피하려고
    경고 채널을 쓴다(`pytest.ini::filterwarnings` 는 이 부류를 거르지 않는다).
    """
    import warnings  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    if seen:
        argv, proc = seen[-1]
        out, err = (proc.stdout or ""), (proc.stderr or "")
        shape = "exit={0} stdout[{1}]={2!r} stderr[{3}]={4!r}".format(
            proc.returncode, len(out), out[:160], len(err), err[:160])
        argv_s = " ".join(str(x) for x in (argv or []))[:120]
    else:
        shape, argv_s = "서브프로세스 미실행", ""
    outcome = ("raise " + type(exc).__name__) if exc else "issues=%d" % len(verdict or [])
    line = "W2-SHAPE tool={0} case={1} | argv={2} | {3} | adapter={4}".format(
        tool, case, argv_s, shape, outcome)
    warnings.warn(line, UserWarning, stacklevel=2)
    print("\n" + line, file=sys.stderr)
    return line


# ── 실측 결과 (CI ubuntu-latest, 실바이너리, 2026-08-30) ──────────────────────
#
# 🔴 **넷 중 둘이 크래시해도 파싱 가능한 출력을 낸다.** 「파싱 불가 = 미분석」 하나로
#    일괄 전환했으면 절반에 틀린 판별식을 실었다 — #1564 가 rubocop 에서 배운 것 그대로다.
#
#   도구            깨끗                     크래시(없는 경로)                    판별식 후보
#   ─────────────────────────────────────────────────────────────────────────────────────
#   cppcheck        exit=0 · stderr 에 XML   exit=1 · stdout 평문, XML **없음**   stderr XML 부재
#   hadolint        exit=0 · stdout `[]`     exit=1 · stdout **빈값**             빈 stdout
#   golangci-lint   exit=0 · JSON            **exit=7 · 유효 JSON `Issues:[]`**   🔴 exit / stderr 필요
#   shellcheck      exit=0 · stdout `[]`     **exit=2 · stdout `[]`**             🔴 exit / stderr 필요
#
#   깨진 입력(`junk`)은 셋에서 **발견**으로 나온다(syntaxError · DL1000 · SC2148) —
#   크래시가 아니다. golangci-lint 만 exit=5 · 빈 stdout 이다.
#
# 즉 cppcheck·hadolint 는 출력 모양만으로 가를 수 있고, golangci-lint·shellcheck 는
# **종료코드 또는 stderr 를 함께 봐야 한다.** 전환 PR 은 도구별로 갈라서 한다.
# Measured in CI: two of four emit parsable output when they crash.


@pytest.mark.parametrize("tool", sorted(_W2_TOOLS))
def test_w2_crash_shape_is_recorded_and_is_still_fail_open(tool, tmp_path):
    """🔴 네 도구의 **크래시 모양을 실측으로 기록**하고, 오늘의 fail-open 을 단언한다.

    세 경우를 잰다 — 깨끗 / 없는 경로 / 도구가 못 읽는 내용. 셋 다 어댑터는 지금 `[]` 를
    돌려준다. 깨끗은 옳고 **나머지 둘은 결함**이다(미분석이 「완전」으로 기록된다).

    관측은 `W2-SHAPE` 로 시작하는 줄로 경고에 남는다 — CI 로그에서 그것을 읽어 도구별
    판별식을 정한다. 그 판별식 없이 전환하면 #1564(rubocop: 크래시해도 유효 JSON) 또는
    slither(#1567: 깨끗한 파일까지 차단)를 재생산한다.
    """
    module_name, class_name, language, ext, clean = _W2_TOOLS[tool]
    _require(tool)
    adapter = _w2_adapter(module_name, class_name)

    stem = "Dockerfile" if tool == "hadolint" else "probe" + ext
    good = tmp_path / stem
    good.write_text(clean, encoding="utf-8")
    junk = tmp_path / (("junk" + ext) if ext else "Dockerfile.junk")
    junk.write_bytes(b"\x00\x01\x02\xff\xfe not a program at all \x00\n")

    cases = {
        "clean": good,
        "missing": tmp_path / (("nope" + ext) if ext else "Dockerfile.nope"),
        "junk": junk,
    }
    for case, path in cases.items():
        ctx = AnalyzeContext(filename=path.name, content=clean, language=language,
                             is_test=False, tmp_path=str(path))
        try:
            seen, verdict, exc = _w2_observe(adapter, ctx)
        except OSError as os_exc:                      # shim 실행 불가 = 플랫폼 한계
            if os.name == "nt":
                _not_measured("Windows 가 %s shim 을 직접 실행 못 함 (%s)"
                              % (tool, type(os_exc).__name__))
            raise
        _w2_record(tool, case, seen, verdict, exc)

        if tool in _W2_CONVERTED and case == "missing":
            # 🔴 전환된 도구는 크래시에서 **올린다** — 그것이 이 작업의 목적이다.
            assert exc is not None, (
                "%s: fail-closed 인데 크래시에서 `[]` 를 돌려줬다 — 판별식(%s)이 "
                "이 크래시 모양을 놓쳤다" % (tool, _W2_CONVERTED[tool])
            )
            assert isinstance(exc, RuntimeError), (
                "%s: 올라온 것이 RuntimeError 가 아니다 — %r" % (tool, exc))
            continue
        assert exc is None, (
            "%s/%s: 어댑터가 이미 raise 한다 — fail-closed 로 전환된 것이다. 이 절을 "
            "`_W2_CONVERTED` 에 등록하고 **어떤 판별식으로 잡았는지** 적어라. (%r)"
            % (tool, case, exc)
        )
        if case == "junk":
            # 🔴 **깨진 입력은 크래시가 아니다** — 실측(CI): cppcheck 는 `syntaxError` 를,
            #    hadolint 는 `DL1000` 을, shellcheck 는 `SC2148` 을 **발견으로 보고**한다.
            #    그것은 도구가 정상 동작한 것이므로 개수를 단언하지 않는다.
            # Broken input is a finding, not a crash: three of four report it as a rule hit.
            assert isinstance(verdict, list), (
                "%s/%s: 목록이 아니다 — %r" % (tool, case, verdict))
        else:
            assert verdict == [], (
                "%s/%s: 예상 밖 결과 %r — 판별식 전제가 깨졌다" % (tool, case, verdict)
            )


@pytest.mark.parametrize("tool", sorted(_W2_TOOLS))
def test_w2_ordinary_dirty_input_must_not_look_like_a_crash(tool, tmp_path):
    """🔴 **과차단 방어** — fail-closed 로 바꿔도 평범한 PR 을 막지 않는지 미리 잰다.

    `test_sqlfluff_parse_failure_is_a_violation_not_a_crash` 와 같은 축이다. 지저분하지만
    정상인 입력에서 도구가 **컨테이너를 내는지**가 판별식의 안전 여부를 가른다 — 안 내면
    「파싱 불가 = 미분석」 판별식이 정상 PR 을 통째로 막는다(#1564 → #1567 의 경로).

    여기가 red 면 그 도구는 **아직 전환하면 안 된다.**
    """
    module_name, class_name, language, ext, _clean = _W2_TOOLS[tool]
    _require(tool)
    adapter = _w2_adapter(module_name, class_name)

    dirty = _W2_DIRTY[tool]
    name = "Dockerfile" if tool == "hadolint" else "dirty" + ext
    src = tmp_path / name
    src.write_text(dirty, encoding="utf-8")

    ctx = AnalyzeContext(filename=name, content=dirty, language=language,
                         is_test=False, tmp_path=str(src))
    try:
        seen, verdict, exc = _w2_observe(adapter, ctx)
    except OSError as os_exc:
        if os.name == "nt":
            _not_measured("Windows 가 %s shim 을 직접 실행 못 함 (%s)"
                          % (tool, type(os_exc).__name__))
        raise
    _w2_record(tool, "dirty", seen, verdict, exc)

    assert exc is None, (
        "%s: 평범한 지저분한 입력에서 raise 했다 — 전환하면 과차단이다 (%r)" % (tool, exc)
    )
    assert isinstance(verdict, list), "%s: 목록이 아니다 — %r" % (tool, verdict)


# ── golangci-lint 전환의 유일한 미측정 축 (#1557 W2) ──────────────────────────
#
# 🔴 #1580 이 잰 두 크래시 모양(없는 경로 · 널바이트)은 **프로덕션에서 발생하지 않는다**:
#      `static.py::        tmp_path = os.path.join(tmpdir, f"analyze{suffix}")` 가 파일을 먼저 쓰고,
#      `golangci_lint.py::def _ensure_go_mod` 가 `module tempmod` 를 자동 생성한다.
#    그래서 그 둘로는 전환 판단을 할 수 없다.
#
# 🔴 프로덕션에서 실제로 일어나는 것은 **형제 패키지를 임포트하는 파일**이다. 이 어댑터는
#    파일 하나를 임시 디렉터리에 떼어 놓고 부르므로, 원본 리포에서 옆 파일을 참조하던
#    코드는 타입체크가 되지 않는다. 그때 golangci-lint 가
#
#      (A) `Issues` 에 typecheck 항목을 담아 준다   -> `issues` 가 비지 않는다 -> 헬퍼 False -> 안전
#      (B) `Issues:[]` + 비-0 종료로 끝낸다          -> 헬퍼 True -> **모든 다중파일 Go PR 이 `incomplete`**
#
#    (B) 이면 전환은 벽이 된다 — #1564 가 slither 에서 낸 사고와 같은 부류다.
#    Grok plan-review `01a050d8` 이 이 축을 「전환 전에 반드시 재야 하는 유일한 사실」로 지목했다.
#
# 🔴 이 시험은 **판단하지 않는다.** 오늘의 동작(`[]`)을 단언하고 모양을 `W2-SHAPE` 로 기록한다.
#    CI 로그에서 그 줄을 읽어 (A)/(B) 를 가른 뒤에 전환 여부를 정한다.
#
# 🔴 **실측 결과 (CI, 2026-08-30) — (B) 였다.**
#      exit=3 · stdout **0바이트** · stderr `level=warning "[runner] Can't run linter
#      goanalysis_metalinter: buildir: failed to load package : could not load export data"`
#      · adapter `issues=0`
#    JSON 봉투가 **아예 안 나왔다** — 즉 「돌 수 있는 린터가 아무것도 못 찾았다」가 아니라
#    기본 린터 전체(v1.55.2 는 errcheck·gosimple·govet·ineffassign·staticcheck·unused·
#    typecheck 가 모두 `goanalysis_metalinter` 안이다)가 실패한 것이고, `issues=0` 은
#    `golangci_lint.py::            if not r.stdout.strip():` 갈래에서 나온 값이다.
#    (Grok claim-review `01a05124` Q4.)
#
# 🔴 그래서 **golangci-lint 는 전환하지 않는다.** `empty_output_is_a_crash` 를 걸면
#    형제를 참조하는 모든 Go 파일이 `incomplete` 가 된다. 종료코드 허용목록(3 은 봐주고
#    5·7 은 올린다)은 이 리포가 반복해 다친 **얼어붙은 목록**이고, stderr 를 보는 것은
#    헬퍼의 계약(「stderr 는 보지 않는다」)을 깬다.
#
# The measured answer is (B): converting would wall every Go file that references anything
# outside itself.


def test_w2_golangci_sibling_import_shape_is_recorded(tmp_path):
    """🔴 형제 패키지를 임포트하는 파일 — 프로덕션에서 실제로 오는 모양이다.

    `_ensure_go_mod` 가 만드는 `module tempmod` 안에서 `tempmod/helper` 는 해석되지만
    그 디렉터리가 없다. 원본 리포의 파일을 하나만 떼어 온 상황과 같다.
    """
    _require("golangci-lint")
    adapter = _w2_adapter("golangci_lint", "_GolangciLintAnalyzer")
    src = tmp_path / "probe.go"
    src.write_text(
        "package main" + chr(10) + chr(10)
        + 'import "tempmod/helper"' + chr(10) + chr(10)
        + "func main() { helper.Do() }" + chr(10),
        encoding="utf-8")

    ctx = AnalyzeContext(filename="probe.go", content=src.read_text(encoding="utf-8"),
                         language="go", is_test=False, tmp_path=str(src))
    try:
        seen, verdict, exc = _w2_observe(adapter, ctx)
    except OSError as os_exc:
        if os.name == "nt":
            _not_measured("Windows 가 golangci-lint 를 직접 실행 못 함 (%s)"
                          % type(os_exc).__name__)
        raise
    _w2_record("golangci-lint", "sibling_import", seen, verdict, exc)

    assert exc is None, (
        "golangci-lint 가 형제 임포트에서 이미 raise 한다 — 전환된 것이다. (%r)" % exc)
    assert isinstance(verdict, list), "목록이 아니다 — %r" % verdict
    # 🔴 개수를 단언하지 않는다. (A) 면 비지 않고 (B) 면 빈다 — **그것이 측정 대상**이다.
    #    `W2-SHAPE` 줄의 `adapter=issues=N` 과 `exit=` 를 CI 로그에서 읽어 판단한다.


# ── golangci-lint: 같은 패키지의 다른 파일을 참조하는 모양 (#1557 W2) ──────────
#
# 🔴 형제 **패키지** 임포트는 이미 쟀고 결과는 (B) 였다 — `exit=3` · stdout **0바이트** ·
#    `issues=0`(#1582 의 `W2-SHAPE`). 그래서 `empty_output_is_a_crash` 로 전환하면
#    형제를 참조하는 모든 Go 파일이 `incomplete` 가 된다. **전환하지 않기로 했다.**
#
# 🔴 그런데 그보다 **훨씬 흔한** 모양이 하나 더 있다. Go 는 같은 패키지의 다른 파일에
#    있는 심볼을 **임포트 없이** 그냥 쓴다. 어댑터는 파일 하나를 임시 디렉터리에 떼어
#    놓으므로 그 심볼이 정의되지 않은 상태가 된다 — 실제 리포의 대다수 파일이 이 모양이다.
#
#    Grok claim-review `01a05124` 의 지적: 형제 임포트는 **패키지 적재** 실패
#    (`buildir` · export data 없음)이고, 같은 패키지 참조는 **경로가 다르다** —
#    한 파일짜리 패키지는 적재에 성공하고 `typecheck` 가 그것을 `Issues` 에 담을 수 있다.
#    둘을 같은 것으로 취급하면 안 된다.
#
#      (A) `Issues` 에 typecheck 항목이 담긴다 -> golangci-lint 는 이 모양에서 **동작한다**
#      (B) `Issues:[]` + 비-0                  -> 대부분의 실물 Go 파일에서 **무동작**이고,
#                                                 그것은 #1565(dotnet_format) 부류다
#
# 🔴 이 시험은 **판단하지 않는다.** 오늘의 동작을 단언하고 모양을 `W2-SHAPE` 로 기록한다.
#
# Same-package references need no import; the one-file package may still load, so this is a
# different code path from the sibling-package case. Measure it before concluding.


def test_w2_golangci_same_package_reference_shape_is_recorded(tmp_path):
    """🔴 같은 패키지의 다른 파일에 있는 심볼을 부르는 파일 — 실물 리포의 대다수 모양이다.

    임포트가 없다. `_ensure_go_mod` 가 만드는 `module tempmod` 안에서 한 파일짜리
    패키지가 되고, `helper()` 는 정의되지 않은 이름이 된다.
    """
    _require("golangci-lint")
    adapter = _w2_adapter("golangci_lint", "_GolangciLintAnalyzer")
    src = tmp_path / "probe.go"
    src.write_text(
        "package tempmod" + chr(10) + chr(10)
        + "func Use() {" + chr(10)
        + chr(9) + "helper()" + chr(10)
        + "}" + chr(10),
        encoding="utf-8")

    ctx = AnalyzeContext(filename="probe.go", content=src.read_text(encoding="utf-8"),
                         language="go", is_test=False, tmp_path=str(src))
    try:
        seen, verdict, exc = _w2_observe(adapter, ctx)
    except OSError as os_exc:
        if os.name == "nt":
            _not_measured("Windows 가 golangci-lint 를 직접 실행 못 함 (%s)"
                          % type(os_exc).__name__)
        raise
    _w2_record("golangci-lint", "same_package_ref", seen, verdict, exc)

    assert exc is None, (
        "golangci-lint 가 같은 패키지 참조에서 이미 raise 한다 — 전환된 것이다. (%r)" % exc)
    assert isinstance(verdict, list), "목록이 아니다 — %r" % verdict
    # 🔴 개수를 단언하지 않는다 — (A)/(B) 를 가르는 것이 이 시험의 목적이다.
    #    `W2-SHAPE` 줄의 `adapter=issues=N` 과 `exit=` 를 CI 로그에서 읽는다.


# ── golangci-lint: 타입 오류가 **다른 린터까지 끈다** (#1584) ──────────────────
#
# 🔴 `#1584` 의 처방(「`FromLinter == "typecheck"` 를 거른다」)이 안전한지는
#    **거른 뒤 남는 것이 있는가**에 달려 있다. 없으면 그 파일은
#    「분석했고 이슈 0건 · 완전」이 되어 코드품질 만점을 받는다 —
#    시끄러운 거짓이 **조용한 거짓**으로 바뀔 뿐이다.
#
# 🔴 golangci-lint v1.55.2 소스가 답을 갖고 있다 (Grok claim-review `01a056e1`):
#    `pkg/golinters/goanalysis/runner_action.go` 는 `act.pkg.IllTyped` 이면
#    **모든 analyzer 를 건너뛴다** — 구문만 보는 `ineffassign`(LoadModeSyntax)도 포함이다.
#    즉 `undefined: helper` 하나로 그 파일의 린터가 전부 죽고, 남는 것은 typecheck 뿐이다.
#    공식 FAQ 도 같은 말을 한다.
#
# 🔴 그러므로 「한 파일에서 공존하는가」는 **잴 필요가 없다** — 러너가 금지한다.
#    잴 가치가 있는 것은 그 구조적 주장이 **실바이너리에서도 참인가**이고,
#    그것은 **짝 대조군**으로만 잰다:
#
#      대조군  helper() 없음 -> 파일이 컴파일된다 -> `ineffassign` 이 발화해야 한다
#      치료군  helper() 있음 -> IllTyped         -> typecheck 만 남아야 한다
#
#    대조군이 발화하지 않으면 치료군의 「typecheck 뿐」은 **아무것도 뜻하지 않는다**
#    (린터가 애초에 안 도는 것과 구별되지 않는다). 그래서 대조군만 단언하고
#    치료군은 기록만 한다 — 오늘의 값을 계약으로 못박지 않기 위해서다.
#
# 🔴 `ineffassign` 을 고른 이유: v1.55.2 의 **기본 활성** 린터이고(어댑터 argv 에
#    `--enable` 이 없다) 타입 정보 없이 제어흐름만으로 판정한다. `gosec` 는 기본이 아니라
#    이 argv 로는 아예 돌지 않는다 — 그것을 쓰면 argv 탓을 현상으로 오독하게 된다.
# 🔴 `x := 1; x = 2; return x` 의 리터럴을 바꾸지 마라. `x := 0` 은 zero-init 이라
#    ineffassign 이 **사용으로 본다**(발화하지 않는다).
#
# The runner skips every analyzer on an ill-typed package, so coexistence is impossible by
# construction. What is worth measuring is the paired control: does the linter fire at all?

_GO_INEFFASSIGN_BODY = (
    chr(9) + "x := 1" + chr(10)
    + chr(9) + "x = 2" + chr(10)
)


def _go_probe(with_undefined_symbol: bool) -> str:
    """같은 본문, `helper()` 유무만 다른 두 파일 — 그 차이 하나가 IllTyped 를 만든다."""
    call = (chr(9) + "helper()" + chr(10)) if with_undefined_symbol else ""
    return (
        "package tempmod" + chr(10) + chr(10)
        + "func Use() int {" + chr(10)
        + _GO_INEFFASSIGN_BODY
        + call
        + chr(9) + "return x" + chr(10)
        + "}" + chr(10)
    )


def _w2_linters(seen) -> object:
    """마지막 서브프로세스 stdout 의 `FromLinter` 분포 — 실패 모양을 서로 구별해 적는다.

    🔴 어댑터의 `AnalysisIssue` 에는 `FromLinter` 가 **저장되지 않는다**
    (`golangci_lint.py::    from_linter = item.get("FromLinter", "")` 는 severity·category 매핑에만 쓴다).
    운영 DB 로는 린터별로 가를 수 없는 이유이고, 그래서 원본 stdout 에서 읽는다.
    """
    import collections  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    if not seen:
        return "서브프로세스 미실행"
    raw = (seen[-1][1].stdout or "").strip()
    if not raw:
        # 🔴 「빈 stdout」과 「Issues:[]」를 같은 `{}` 로 적지 않는다 — 전자는 도구가 죽은
        #    것이고 후자는 돌았는데 못 찾은 것이다. 한 줄만 보고 결론내지 못하게 가른다.
        return "빈 stdout (도구가 출력을 내지 않았다)"
    try:
        return dict(collections.Counter(
            i.get("FromLinter", "") for i in (json.loads(raw).get("Issues") or [])))
    except (ValueError, AttributeError) as exc:
        return "JSON 읽기 실패: %s" % type(exc).__name__


def _w2_observe_go(tmp_path, source: str):
    """프로덕션 경로로 한 번 태우고 `(seen, verdict, exc)` 를 낸다."""
    adapter = _w2_adapter("golangci_lint", "_GolangciLintAnalyzer")
    src = tmp_path / "probe.go"
    src.write_text(source, encoding="utf-8")
    ctx = AnalyzeContext(filename="probe.go", content=source,
                         language="go", is_test=False, tmp_path=str(src))
    try:
        return _w2_observe(adapter, ctx)
    except OSError as os_exc:
        if os.name == "nt":
            _not_measured("Windows 가 golangci-lint 를 직접 실행 못 함 (%s)"
                          % type(os_exc).__name__)
        raise


def _record_linters(case: str, seen) -> None:
    import warnings  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    line = "W2-LINTERS tool=golangci-lint case={0} | linters={1}".format(case, _w2_linters(seen))
    warnings.warn(line, UserWarning, stacklevel=2)
    print("\n" + line, file=sys.stderr)


def test_w2_golangci_control_a_compiling_file_does_report_ineffassign(tmp_path):
    """🔴 **대조군 — 이 단언이 없으면 아래 치료군은 아무것도 뜻하지 않는다.**

    타입이 맞는 파일에서 `ineffassign` 이 발화하는지 본다. 발화하지 않으면
    「치료군에 typecheck 뿐」은 「린터가 애초에 안 돈다」와 구별되지 않는다.
    """
    _require("golangci-lint")
    seen, verdict, exc = _w2_observe_go(tmp_path, _go_probe(with_undefined_symbol=False))
    _w2_record("golangci-lint", "control_compiles", seen, verdict, exc)
    _record_linters("control_compiles", seen)

    assert exc is None, "대조군에서 raise 했다 — 측정이 성립하지 않는다. (%r)" % exc
    assert "ineffassign" in (_w2_linters(seen) or {}), (
        "컴파일되는 파일에서 `ineffassign` 이 발화하지 않았다 — 이 프로브로는 "
        "`#1584` 의 축을 잴 수 없다.\n"
        "  기본 린터 집합·argv·프로브 본문 중 무엇이 바뀌었는지 확인할 것 "
        "(`x := 0` 은 zero-init 이라 발화하지 않는다).\n"
        "  분포: %r" % (_w2_linters(seen),)
    )


def test_w2_golangci_an_ill_typed_file_shape_is_recorded(tmp_path):
    """🔴 치료군 — `undefined:` 하나가 있는 같은 파일. **판단하지 않고 기록한다.**

    구조적 예측은 「typecheck 뿐」이다(`runner_action.go` 의 `IllTyped` 건너뛰기).
    그 예측이 실바이너리에서도 참이면 `#1584` 의 필터-만(A1)은 그 파일을
    **이슈 0건 · 완전**으로 만든다 — 처방은 A2(필터 + 신호)여야 한다.

    🔴 여기서 오늘의 값을 단언하지 않는다. 상류가 `RunDespiteErrors` 를 존중하도록
    바뀌면 그것은 **개선**인데, 못박아 두면 그 개선이 red 가 된다.
    """
    _require("golangci-lint")
    seen, verdict, exc = _w2_observe_go(tmp_path, _go_probe(with_undefined_symbol=True))
    _w2_record("golangci-lint", "ill_typed", seen, verdict, exc)
    _record_linters("ill_typed", seen)

    assert exc is None, (
        "golangci-lint 가 이 모양에서 이미 raise 한다 — 전환된 것이다. (%r)" % exc)
    assert isinstance(verdict, list), "목록이 아니다 — %r" % verdict
