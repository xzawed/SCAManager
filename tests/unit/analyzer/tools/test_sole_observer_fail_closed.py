"""관측면이 하나뿐인 언어의 어댑터는 실패를 삼키지 않는다 (#1521 W1 / #1557).

`static.py::_run_analyzers` 의 계약: `run()` 이 **예외를 올릴 때만** `incomplete` 로 승격한다.
`[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.

여기 5개는 그 언어의 **유일한** 관측면이다(실측 — css·scss·dart·hcl·powershell·protobuf 는
`SUPPORTED_LANGUAGES` 를 선언한 다른 어댑터가 없다). 이들이 눈이 멀면 대체할 것이 없다.

## 🔴 크래시 판별식은 exit code 가 아니다

린터는 **이슈를 찾으면 비-0 으로 끝난다**. 판별식은 「기대한 형식의 출력을 냈는가」이고
그 형식이 도구마다 다르다. 이 파일이 두 부류를 나눠 재는 이유다:

    CONTAINER    깨끗해도 봉투를 낸다   → 봉투가 아니면(빈 출력 포함) raise
    EMPTY_LEGAL  깨끗하면 빈 출력이다   → 빈 출력 + 비-0 일 때만 raise

`EMPTY_LEGAL` 을 `CONTAINER` 처럼 다루면 **깨끗한 파일이 전부 incomplete** 가 된다.
실측 근거: `@() | ConvertTo-Json -AsArray` 는 `[]` 가 아니라 **$null** 을 낸다(pwsh 로 확인).
buf 는 JSONL 이라 형식 정의상 깨끗하면 빈 출력이다.

`CONTAINER` 쪽 근거: `tests/integration/test_contracted_analyzers_real_binary.py` 의
`test_tflint_output_starts_with_a_brace_and_carries_the_issues_envelope` 가 실 바이너리로
「이슈 0건이어도 `{` 봉투를 낸다」를 잰다.

🔴 stylelint·dart 의 깨끗한 출력은 **로컬에서 재지 못했다**(바이너리 부재). 문서상 컨테이너
형식이라 그렇게 다룬다. 틀렸다면 그 언어의 깨끗한 파일이 `incomplete` 가 된다 — 시끄러운
오류이지 조용한 통과가 아니다.

정본 판정은 `tests/unit/analyzer/test_adapter_fail_open_inventory.py::_fail_open_reasons` 다.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

from src.analyzer.pure.registry import REGISTRY, AnalyzeContext

CONTAINER = "container"
EMPTY_LEGAL = "empty-legal"


@dataclass(frozen=True)
class Adapter:
    """한 어댑터의 계약. `clean_stdout` 은 「이슈 0건」일 때 도구가 실제로 내는 것."""

    tool: str
    cls: str
    language: str
    filename: str
    kind: str
    clean_stdout: str
    dirty_stdout: str
    dirty_exit: int


ADAPTERS: tuple[Adapter, ...] = (
    Adapter("stylelint", "_StylelintAnalyzer", "css", "a.css", CONTAINER,
            "[]",
            json.dumps([{"warnings": [{"text": "x", "line": 3, "severity": "error"}]}]), 2),
    Adapter("dart_analyze", "_DartAnalyzer", "dart", "a.dart", CONTAINER,
            '{"diagnostics":[]}',
            json.dumps({"diagnostics": [{"severity": "ERROR", "problemMessage": "x",
                                         "location": {"range": {"start": {"line": 3}}}}]}), 3),
    Adapter("tflint", "_TflintAnalyzer", "terraform", "a.tf", CONTAINER,
            '{"issues":[]}',
            json.dumps({"issues": [{"message": "x", "rule": {"severity": "error"},
                                    "range": {"start": {"line": 3}}}]}), 2),
    Adapter("psscriptanalyzer", "_PSScriptAnalyzer", "powershell", "a.ps1", EMPTY_LEGAL,
            "", json.dumps([{"Severity": 1, "Message": "x", "Line": 3}]), 0),
    Adapter("buf_lint", "_BufLintAnalyzer", "protobuf", "a.proto", EMPTY_LEGAL,
            "", json.dumps({"message": "x", "start_line": 3}), 100),
)

IDS = [a.tool for a in ADAPTERS]
CONTAINERS = [a for a in ADAPTERS if a.kind == CONTAINER]
CONTAINER_IDS = [a.tool for a in CONTAINERS]
EMPTY_LEGALS = [a for a in ADAPTERS if a.kind == EMPTY_LEGAL]
EMPTY_LEGAL_IDS = [a.tool for a in EMPTY_LEGALS]


def _ctx(a: Adapter) -> AnalyzeContext:
    return AnalyzeContext(filename=a.filename, content="", language=a.language,
                          is_test=False, tmp_path=f"/tmp/{a.filename}")


def _proc(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.stdout, m.stderr, m.returncode = stdout, stderr, returncode
    return m


def _analyzer(a: Adapter):
    mod = __import__(f"src.analyzer.io.tools.{a.tool}", fromlist=[a.cls])
    return getattr(mod, a.cls)()


def _run(a: Adapter, proc=None, side_effect=None, ctx=None):
    """어댑터를 실행한다. `shutil.which` 는 항상 통과시켜 is_enabled 축을 분리한다."""
    kw = {"side_effect": side_effect} if side_effect is not None else {"return_value": proc}
    with patch("shutil.which", return_value="/usr/bin/tool"):
        with patch("subprocess.run", **kw):
            return _analyzer(a).run(ctx if ctx is not None else _ctx(a))


@pytest.fixture(autouse=True)
def _isolate_registry():
    before = list(REGISTRY)
    yield
    REGISTRY.clear()
    REGISTRY.extend(before)


# ─── 1. 봉투형 — 빈 출력은 깨끗함이 아니라 미분석이다 ────────────────────────


@pytest.mark.parametrize("a", CONTAINERS, ids=CONTAINER_IDS)
def test_container_tool_raises_on_empty_stdout_even_with_exit_zero(a: Adapter):
    """봉투를 내는 도구가 아무것도 내지 않았으면 분석이 일어나지 않은 것이다.

    🔴 이 시험이 명세의 함정이다 — 기존 `test_returns_empty_on_empty_output` 이
    정확히 반대를 보증하고 있었다.
    """
    proc = _proc("", 0)
    with pytest.raises(RuntimeError):
        _run(a, proc)


@pytest.mark.parametrize("a", CONTAINERS, ids=CONTAINER_IDS)
def test_container_tool_raises_on_non_container_stdout(a: Adapter):
    """도구가 사람이 읽는 오류 텍스트를 냈으면 파싱 실패가 아니라 미분석이다."""
    proc = _proc("error: could not load config\n", 1)
    with pytest.raises(RuntimeError):
        _run(a, proc)


@pytest.mark.parametrize("a", CONTAINERS, ids=CONTAINER_IDS)
def test_clean_container_returns_no_issues_without_raising(a: Adapter):
    """빈 봉투는 진짜로 깨끗한 것이다 — 여기서 올리면 과차단이다."""
    assert _run(a, _proc(a.clean_stdout, 0)) == []


# ─── 2. 빈 출력 합법형 — 깨끗함과 크래시를 exit 로 가른다 ────────────────────


@pytest.mark.parametrize("a", EMPTY_LEGALS, ids=EMPTY_LEGAL_IDS)
def test_empty_legal_tool_treats_empty_stdout_with_exit_zero_as_clean(a: Adapter):
    """깨끗한 입력을 막지 않는다 — 과차단이 이 작업의 주된 위험이다."""
    assert _run(a, _proc("", 0)) == []


@pytest.mark.parametrize("a", EMPTY_LEGALS, ids=EMPTY_LEGAL_IDS)
def test_empty_legal_tool_stays_clean_when_stderr_carries_noise(a: Adapter):
    """stderr 에 안내문이 있다고 크래시로 보지 않는다.

    정본은 `python.py` 의 `if not issues and r.returncode != 0` (flake8) 과 `tsc.py` 다 —
    둘 다 stderr 를 보지 않는다. stderr 를 조건에 넣으면 정상 파일이 차단된다.
    """
    assert _run(a, _proc("", 0, "warning: using default config\n")) == []


@pytest.mark.parametrize("a", EMPTY_LEGALS, ids=EMPTY_LEGAL_IDS)
def test_empty_legal_tool_raises_on_empty_stdout_with_nonzero_exit(a: Adapter):
    """아무것도 못 읽었는데 비정상 종료 = 미분석.

    실측: PSScriptAnalyzer 모듈이 없는 머신에서 `Invoke-ScriptAnalyzer` 는 exit 1 로
    죽고 stdout 이 비어 있다. 지금은 그것이 「이슈 0건」으로 기록된다.
    """
    proc = _proc("", 1, "command not found\n")
    with pytest.raises(RuntimeError):
        _run(a, proc)


# ─── 3. 이슈를 찾은 것은 크래시가 아니다 ─────────────────────────────────────


@pytest.mark.parametrize("a", ADAPTERS, ids=IDS)
def test_nonzero_exit_with_findings_is_not_a_crash(a: Adapter):
    """린터는 이슈를 찾으면 비-0 으로 끝난다 — 그것으로 실패를 판정하면 안 된다."""
    issues = _run(a, _proc(a.dirty_stdout, a.dirty_exit))
    assert len(issues) == 1, f"{a.tool}: 이슈를 파싱하지 못했다"
    assert issues[0].line == 3


# ─── 4. 예외 축 — 좁은 두 축만 `[]` 로 남는다 ────────────────────────────────


@pytest.mark.parametrize("a", ADAPTERS, ids=IDS)
def test_timeout_returns_empty_and_marks_the_context(a: Adapter):
    """타임아웃은 `ctx.timed_out` 이 담당하는 정당한 축이다."""
    ctx = _ctx(a)
    assert _run(a, side_effect=subprocess.TimeoutExpired(a.tool, 30), ctx=ctx) == []
    assert ctx.timed_out is True


@pytest.mark.parametrize("a", ADAPTERS, ids=IDS)
def test_file_not_found_returns_empty(a: Adapter):
    """스폰 시점의 바이너리 부재는 조달 축(`unavailable_tools`)이 담당한다."""
    assert _run(a, side_effect=FileNotFoundError("no such binary")) == []


@pytest.mark.parametrize("a", ADAPTERS, ids=IDS)
def test_permission_error_raises(a: Adapter):
    """깨진 shebang · 권한 오류는 「바이너리 부재」가 아니라 미분석이다."""
    boom = PermissionError("exec format error")
    with pytest.raises(OSError):
        _run(a, side_effect=boom)


@pytest.mark.parametrize("a", CONTAINERS, ids=CONTAINER_IDS)
def test_container_tool_raises_on_malformed_json_after_a_valid_prefix(a: Adapter):
    """봉투로 시작했지만 파싱이 안 되면 이슈를 못 읽은 것이다."""
    proc = _proc(a.clean_stdout[0] + '{"broken', 0)
    with pytest.raises(RuntimeError):
        _run(a, proc)


@pytest.mark.parametrize("a", EMPTY_LEGALS, ids=EMPTY_LEGAL_IDS)
def test_empty_legal_tool_raises_on_unparsable_nonempty_stdout(a: Adapter):
    """빈 출력이 합법이라고 **아무 출력**이나 합법인 것은 아니다.

    실측: 모듈 없는 pwsh 는 `Invoke-ScriptAnalyzer: ... not recognized` 를 낸다.
    """
    proc = _proc("Invoke-ScriptAnalyzer: not recognized\n", 0)
    with pytest.raises(RuntimeError):
        _run(a, proc)


# 도구가 기대하는 것과 **반대 모양**의 유효한 JSON. 파싱은 되지만 이 도구의 출력이 아니다.
_WRONG_SHAPE = {
    "stylelint": '{"warnings":[]}',        # 배열을 기대하는데 객체
    "dart_analyze": "[]",                  # 객체를 기대하는데 배열
    "tflint": "[]",                        # 객체를 기대하는데 배열
    "psscriptanalyzer": '{"Severity":1}',  # 배열을 기대하는데 객체
}


@pytest.mark.parametrize("tool,payload", sorted(_WRONG_SHAPE.items()))
def test_valid_json_of_the_wrong_shape_raises_a_named_failure(tool: str, payload: str):
    """🔴 이 시험이 없으면 봉투 가드는 **죽은 코드**다 (뮤테이션으로 확인).

    빈 출력·오류 텍스트는 `json.loads` 가 `JSONDecodeError` 를 내고 그 핸들러가 이미
    raise 로 바꾼다. 봉투 가드를 `if False` 로 죽여도 그 시험들은 전부 통과했다.
    가드가 홀로 지키는 것은 **파싱은 되지만 이 도구의 출력이 아닌** 입력이다 —
    가드가 없으면 반복 중 `AttributeError` 로 터져 사유를 잃는다.
    """
    a = next(x for x in ADAPTERS if x.tool == tool)
    proc = _proc(payload, 0)
    with pytest.raises(RuntimeError):
        _run(a, proc)


def test_buf_lint_raises_on_malformed_jsonl_line():
    """한 줄이 깨졌으면 그 줄의 이슈가 사라진 것이다 — 조용히 건너뛰지 않는다.

    이 형태는 `tests/unit/analyzer/fixtures/failopen_shapes/shape_silent_accumulator.py` 에
    픽스처로 박혀 있다.
    """
    a = next(x for x in ADAPTERS if x.tool == "buf_lint")
    proc = _proc('{"message":"ok","start_line":1}\nnot json at all\n', 100)
    with pytest.raises(RuntimeError):
        _run(a, proc)


# ─── 5. 예외가 `incomplete` 에 실제로 닿는가 ─────────────────────────────────


def _analyze(a: Adapter, proc, content: str = "x\n"):
    """`analyze_file` 을 태운다. pssa 는 능력 탐지가 같은 mock 을 쓰므로 따로 켠다."""
    from src.analyzer.io.static import analyze_file
    from src.analyzer.io.tools import psscriptanalyzer as pssa

    with patch("shutil.which", return_value="/usr/bin/tool"):
        with patch.object(pssa, "psscriptanalyzer_module_available", return_value=True):
            with patch("subprocess.run", return_value=proc):
                return analyze_file(a.filename, content)


@pytest.mark.parametrize("a", ADAPTERS, ids=IDS)
def test_a_crash_reaches_the_incomplete_marker(a: Adapter):
    """🔴 이 작업의 목적은 어댑터가 올리는 것이 아니라 게이트가 막는 것이다.

    `static.py::_run_analyzers` 가 예외를 `incomplete` 로 승격하지 않으면 auto-merge 는
    그대로 열려 있다. 어댑터 단위 시험만으로는 그것이 증명되지 않는다.
    """
    result = _analyze(a, _proc("garbage that is not the expected format", 1))
    assert result.incomplete is True, f"{a.tool}: 크래시가 incomplete 로 승격되지 않았다"


@pytest.mark.parametrize("a", ADAPTERS, ids=IDS)
def test_a_clean_run_does_not_reach_the_incomplete_marker(a: Adapter):
    """과차단 가드 — 깨끗한 입력이 `incomplete` 를 켜면 그 언어의 게이트가 통째로 막힌다."""
    result = _analyze(a, _proc(a.clean_stdout, 0))
    assert result.incomplete is False, f"{a.tool}: 깨끗한 입력을 incomplete 로 막았다"


# ─── 6. 능력 부재는 미분석이 아니라 미제공이다 ───────────────────────────────


@pytest.fixture(autouse=True)
def _clear_pssa_probe_cache():
    """모듈 탐지는 프로세스당 한 번만 물으므로 테스트 사이에 비운다."""
    from src.analyzer.io.tools import psscriptanalyzer as m

    m.psscriptanalyzer_module_available.cache_clear()
    yield
    m.psscriptanalyzer_module_available.cache_clear()


def _pssa_is_enabled(probe) -> bool:
    from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer

    a = next(x for x in ADAPTERS if x.tool == "psscriptanalyzer")
    with patch("shutil.which", return_value="/usr/bin/pwsh"):
        with patch("subprocess.run", return_value=probe):
            return _PSScriptAnalyzer().is_enabled(_ctx(a))


def test_psscriptanalyzer_is_disabled_when_the_module_is_absent():
    """`pwsh` 가 있어도 PSScriptAnalyzer **모듈**이 없으면 돌릴 수 없다.

    🔴 이것은 `run()` 의 raise 로 다루면 안 된다. 모듈 없는 호스트에서는 **모든**
    PowerShell 파일이 `incomplete` 가 되어 그 배포의 게이트가 통째로 막힌다.
    미제공은 `static.py` 의 `uncovered_language` 축이 담당한다.

    실측(이 개발 PC — pwsh 있음 · 모듈 없음): `Invoke-ScriptAnalyzer` 는 exit 1 로
    죽고 stdout 이 비었다. 지금까지 그것이 「이슈 0건」으로 기록됐다.
    """
    assert _pssa_is_enabled(_proc("", 1, "not recognized")) is False


def test_psscriptanalyzer_is_enabled_when_the_module_is_present():
    """모듈이 있으면 켜진다 — 위 시험이 항상-False 로 공허해지지 않게 못 박는다."""
    assert _pssa_is_enabled(_proc("PSScriptAnalyzer\n", 0)) is True


def test_psscriptanalyzer_is_disabled_when_the_probe_itself_fails():
    """탐지 자체가 실패하면 켜지 않는다 — 모르면 끄는 쪽이다(fail-closed)."""
    from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer

    a = next(x for x in ADAPTERS if x.tool == "psscriptanalyzer")
    with patch("shutil.which", return_value="/usr/bin/pwsh"):
        with patch("subprocess.run", side_effect=OSError("spawn failed")):
            assert _PSScriptAnalyzer().is_enabled(_ctx(a)) is False


def test_psscriptanalyzer_probe_is_asked_once_per_process():
    """파일마다 pwsh 를 띄우지 않는다 — is_enabled 는 파일당 호출된다."""
    from src.analyzer.io.tools.psscriptanalyzer import _PSScriptAnalyzer

    a = next(x for x in ADAPTERS if x.tool == "psscriptanalyzer")
    with patch("shutil.which", return_value="/usr/bin/pwsh"):
        with patch("subprocess.run", return_value=_proc("PSScriptAnalyzer\n", 0)) as run:
            for _ in range(3):
                _PSScriptAnalyzer().is_enabled(_ctx(a))
    assert run.call_count == 1, f"모듈 탐지를 {run.call_count}회 물었다"
