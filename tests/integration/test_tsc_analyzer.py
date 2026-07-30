"""tsc 분석기 실바이너리 통합 테스트 (#1238 — #1226 동일 클래스).

🔴 왜 이 파일이 필요한가 — `tests/unit/analyzer/tools/test_tsc.py` 는 `subprocess.run` 을 전부
mock 하므로 **"argv 가 어떻게 조립됐는가" 만** 검증한다. 그래서 tsc 가 실제로는 아무것도 분석하지
못하는 상태여도 단위 테스트는 전건 통과한다 — eslint(#1226)에서 단위 40건이 green 인 채 운영이
100% 무동작이었던 것과 **완전히 같은 구조**다.

## 이 파일이 잡는 결함

`railway.toml:3` 은 `npm install -g typescript` 를 **버전 핀 없이** 설치한다. major 버전이 drift 해
CLI 플래그가 바뀌면 tsc 는 진단 대신 `error TS5023: Unknown compiler option '--x'.` 를 뱉는데,
그 출력에는 `file(line,col):` 접두가 없어 `_TSC_DIAG_RE` 에 **걸리지 않는다** → 이슈 0건 →
"분석했더니 깨끗함" 과 구별 불가 → 정적 만점 → 점수 인플레가 auto-merge 까지 전파.

실측(2026-07-31, typescript 5.9.3):

| 케이스 | exit | 정규식 매치 | 수정 전 | 수정 후 |
|--------|------|-------------|---------|---------|
| 정상 코드 | 0 | — | `[]` | `[]` (보존) |
| 타입 오류 | 2 | ✅ | 이슈 | 이슈 |
| **무효 플래그** | **1** | ❌ | **`[]` 🔴** | `RuntimeError` → incomplete |

## 계약

`returncode != 0` 인데 파싱된 진단이 **0건**이면 `RuntimeError` — `static.py` 의 broad-except 가
`incomplete=True` 로 승격해 auto-merge/auto-approve 를 차단한다. `exit 0 + 진단 0` 은 진짜
깨끗함이므로 raise 하지 않는다(정상 경로 보존).
"""
import os
import pathlib
import shutil
import subprocess  # nosec B404
import tempfile

import pytest

from src.analyzer.io.tools.tsc import _TscAnalyzer
from src.analyzer.pure.registry import AnalyzeContext

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_TSC_JS = _REPO_ROOT / "node_modules" / "typescript" / "bin" / "tsc"

pytestmark = pytest.mark.slow


def _tsc_argv() -> list[str] | None:
    """실행 가능한 tsc 진입점 — PATH 전역본 우선, 없으면 리포 로컬 node_modules.

    Resolve a runnable tsc: prefer the global binary (what production uses), else the repo-local one.
    """
    if shutil.which("tsc"):
        return ["tsc"]
    node = shutil.which("node")
    if node and _TSC_JS.exists():
        return [node, str(_TSC_JS)]
    return None


_ARGV = _tsc_argv()
_SKIP = pytest.mark.skipif(_ARGV is None, reason="tsc 바이너리·node_modules 부재 — 실바이너리 테스트 skip")


def _run(argv_extra: list[str], src: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "probe.ts")
        with open(p, "w", encoding="utf-8") as f:
            f.write(src)
        return subprocess.run(  # nosec B603
            _ARGV + ["--noEmit", "--strict", "--skipLibCheck"] + argv_extra + [p],
            capture_output=True, text=True, timeout=120, check=False,
        )


@_SKIP
def test_clean_source_exits_zero():
    """전제 고정 — 정상 코드는 exit 0. 이게 깨지면 아래 fail-closed 규칙의 근거가 사라진다."""
    r = _run([], "const x: number = 1;\nexport {};\n")
    assert r.returncode == 0, f"정상 코드가 비-0 종료: {(r.stderr or r.stdout)[:200]}"


@_SKIP
def test_type_error_is_reported_as_issue():
    """🔴 분석기가 **실제로 이슈를 산출**하는가 — mock 이 원리적으로 증명 못 하는 축."""
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "bad.ts")
        with open(p, "w", encoding="utf-8") as f:
            f.write("const x: number = 'not-a-number';\nexport {};\n")
        ctx = AnalyzeContext(
            filename="bad.ts", content="", language="typescript",
            is_test=False, tmp_path=p, repo_config=None,
        )
        if not shutil.which("tsc"):
            pytest.skip("전역 tsc 부재 — _TscAnalyzer.run 은 PATH 의 'tsc' 를 호출한다")
        issues = _TscAnalyzer().run(ctx)
    assert issues, "타입 오류가 있는데 이슈 0건 — 분석기가 무동작이다(#1226 클래스)"
    assert any("TS2322" in i.message or "not assignable" in i.message for i in issues), (
        f"기대한 진단이 없다: {[i.message for i in issues]}"
    )


@_SKIP
def test_unknown_flag_produces_unparsable_output_at_nonzero_exit():
    """🔴 결함의 **전제** 실증 — 무효 플래그는 exit≠0 이면서 진단 정규식에 안 걸리는 출력을 낸다.

    이 전제가 참이라야 `returncode != 0 and not issues` 라는 fail-closed 조건이 의미를 가진다.
    """
    r = _run(["--definitelyNotARealFlag"], "const x: number = 1;\n")
    out = (r.stderr or r.stdout).strip()
    assert r.returncode != 0, "무효 플래그인데 exit 0 — 전제가 깨졌다"
    assert "TS5023" in out or "Unknown compiler option" in out, f"예상 밖 출력: {out[:200]}"
    # 🔴 핵심 — 이 출력에는 `file(line,col):` 접두가 없어 진단 정규식이 잡지 못한다.
    from src.analyzer.io.tools.tsc import _TSC_DIAG_RE  # pylint: disable=import-outside-toplevel
    assert not _TSC_DIAG_RE.findall(out), (
        "정규식이 이 출력을 잡는다면 결함 전제가 무효 — 조건을 재설계해야 한다"
    )


@_SKIP
def test_analyzer_raises_instead_of_returning_clean_when_tsc_is_broken(monkeypatch):
    """🔴 봉인 본체 — tsc 가 비정상 종료 + 진단 0건이면 `[]`(깨끗함) 대신 raise 해야 한다.

    수정 전에는 `[]` 를 반환해 정적 만점 → 점수 인플레 → auto-merge 로 전파됐다.
    `static.py` 의 broad-except 가 이 예외를 `incomplete=True` 로 승격한다.
    """
    real_run = subprocess.run

    def _broken(cmd, **kw):
        # 실 tsc 를 **무효 플래그와 함께** 호출 — 실제 깨진 tsc 의 출력을 그대로 재현한다
        # (합성 픽스처 금지: 3-불변식 ② 실경로 뮤테이션).
        return real_run(_ARGV + ["--definitelyNotARealFlag"] + list(cmd[1:]), **kw)

    monkeypatch.setattr("src.analyzer.io.tools.tsc.subprocess.run", _broken)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "probe.ts")
        with open(p, "w", encoding="utf-8") as f:
            f.write("const x: number = 1;\n")
        ctx = AnalyzeContext(
            filename="probe.ts", content="", language="typescript",
            is_test=False, tmp_path=p, repo_config=None,
        )
        with pytest.raises(RuntimeError, match="no parsable diagnostics"):
            _TscAnalyzer().run(ctx)


@_SKIP
def test_clean_run_does_not_raise(monkeypatch):
    """대조군 — exit 0 + 진단 0 은 **진짜 깨끗함**이므로 raise 하지 않는다(정상 경로 보존)."""
    real_run = subprocess.run

    def _local(cmd, **kw):
        return real_run(_ARGV + list(cmd[1:]), **kw)

    monkeypatch.setattr("src.analyzer.io.tools.tsc.subprocess.run", _local)
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "clean.ts")
        with open(p, "w", encoding="utf-8") as f:
            f.write("const x: number = 1;\nexport {};\n")
        ctx = AnalyzeContext(
            filename="clean.ts", content="", language="typescript",
            is_test=False, tmp_path=p, repo_config=None,
        )
        assert _TscAnalyzer().run(ctx) == [], "정상 코드에서 이슈가 나오면 오탐이다"
