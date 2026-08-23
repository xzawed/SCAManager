"""`analyze_file` 입력 다양성 매트릭스 — 경로 종류 × 실패 시점 (#1433 조치 4).

## 왜 이 파일이 따로 있나

`src/analyzer/io/static.py` 는 **조건 완화가 반복된 파일**이다. 최근 8커밋 중 4건:

    #1245  미지원 언어 21종을 «차단 없이 가시화» 로 완화
    #1261  조달되지 않는 분석기의 영구 차단을 완화
    #1410  «semgrep 만 돌면 통과» 를 닫으려 `ran == 0` 게이트를 완화
    #1411  그 완화가 **모든 파이썬 테스트 파일을 incomplete** 로 만들어 긴급 복구

`#1411` 이 이 파일의 존재 이유다. `#1410` 은 뮤테이션 red 와 7084 passed 를 근거로
「봉인」을 발행했는데, **테스트 파일 경로를 입력으로 준 적이 한 번도 없었다.** 회귀는
저자가 상상한 실패 모드가 아니라 **테스트에 준 적 없는 입력 클래스**에서 났다(#1433).

## 이 파일이 고정하는 것

기존 테스트는 **시나리오별로 파일 하나씩**을 본다(`src/app.py` 또는 `app.py`).
여기서는 두 축을 **곱한다** — 한 축만 보면 아래 비대칭이 보이지 않는다:

| 도구 부재 | 테스트 파일 | 생산 파일 |
|---|---|---|
| pylint  | incomplete | incomplete |
| flake8  | incomplete | incomplete |
| bandit  | **정상**   | incomplete |

bandit 만 다른 이유는 `supports()` 가 테스트 파일을 제외하기 때문이다 — 즉 부재해도
`unavailable_tools` 에 들어가지 않는다. 이 비대칭을 모르고 승격 조건을 만지면 `#1411`
이 그대로 재발한다.

Multiplies path-kind × failure-timing instead of testing one file per scenario; the bandit
asymmetry (absent → not incomplete for test files only) is invisible on a single axis.
"""
import shutil
import subprocess
from unittest.mock import patch

import pytest

from src.analyzer.io.static import PROVISIONED_ANALYZERS, analyze_file
from src.analyzer.pure.language import is_test_file

_CODE = "x = 1\n"

# 🔴 파이썬 테스트 판정 규칙 3갈래를 **각각** 통과하는 경로 + 그 경계.
#    규칙: `name.startswith("test_")` 또는 `name.endswith("_test.py")` 또는 `"tests" in parts`
_PATHS = [
    "tests/unit/test_foo.py",   # 접두사 + 디렉토리 (둘 다)
    "test_foo.py",              # 접두사만 (루트)
    "foo_test.py",              # 접미사만
    "tests/conftest.py",        # 디렉토리만 — 이름엔 test 가 없다
    "e2e/test_smoke.py",        # 접두사, tests/ 밖
    "src/app.py",               # 생산 파일
    "src/testing_utils.py",     # 🔴 이름이 test 로 **시작하지 않는다** — 경계(생산 파일)
]


def _is_test(path: str) -> bool:
    """경로 종류 판정 — 이 축은 프로덕션 판정기를 그대로 쓴다(분류기가 틀리면 양쪽이 함께 틀린다)."""
    return is_test_file(path, "python")


def _tool_applies(tool: str, path: str) -> bool:
    """이 도구가 이 파일에 **적용되는가** — 부재 시 incomplete 로 승격될 대상인가.

    🔴 **의도적으로 손으로 적은 규칙이다 — `_BanditAnalyzer().supports()` 를 부르지 마라.**
    (Grok claim-review `01a0101a` 정정: 초판 주석은 "프로덕션에서 파생한다" 고 적었는데
     거짓이었고, 더 중요하게는 **파생하면 안 된다**.)

    `supports()` 에서 파생하면 이 기대값은 프로덕션 규칙과 **함께 움직인다** — 누가
    `supports` 의 테스트 파일 제외를 지우는 순간 기대값도 같이 뒤집혀 뮤테이션이 **조용히
    통과**한다. 그게 `#1411` 을 놓친 형태다. 여기서 손유지는 결함이 아니라 **독립 오라클**이고,
    규칙을 바꾸려면 사람이 이 함수도 함께 고쳐야 한다는 강제가 이 테스트의 값어치다.

    Deliberately hand-written: deriving it from supports() would make the expectation move with
    the bug, which is exactly how #1411 slipped through. This is an independent oracle.
    """
    return not (tool == "bandit" and _is_test(path))


@pytest.fixture(name="no_subprocess")
def _no_subprocess():
    """실바이너리를 태우지 않는다 — 이 파일이 재는 것은 **승격 판정**이지 린터가 아니다.

    🔴 왜 스텁인가 (실측): 실바이너리로 돌리면 이 파일 하나가 **214초** 다(경로 7 × 도구 3
    조합에 `analyze_file` 이 42회, 매번 subprocess 3개). 단위 스위트 전체가 ~250초이므로
    두 배가 된다 — 그러면 아무도 로컬에서 안 돌리고, 그건 가드가 없는 것과 같다(정책 17).

    🔴 무엇을 잃는가 (정직 기준): 린터가 **실제로 이슈를 내는지**는 여기서 재지 않는다.
    그 축은 `tests/integration/test_static_analyzer.py` 가 실바이너리로 덮는다.
    여기서 재는 것은 「어떤 입력 조합이 어떤 판정으로 가는가」뿐이다.

    🔴 **스텁 출력은 도구별 실제 clean 출력이어야 한다.** 초판은 전 도구에 빈 stdout 을
    돌려주고 「도구는 돌았고 이슈는 0」이라 적었는데, 그것은 어댑터가 파싱 실패를 삼켜
    `[]` 를 돌려주던 **결함에 기댄 전제**였다. 실측 clean 출력은 pylint `[]`,
    bandit·semgrep `{...}`, flake8 는 빈 stdout + exit 0 이다. 「빈 stdout + JSON 도구」는
    프로덕션에서 나올 수 없는 조합이고 이제 fail-closed 로 승격되므로, 그 조합을 스텁이
    계속 먹이면 이 파일은 **판정이 아니라 옛 결함**을 재고 있게 된다.
    Per-tool realistic clean output; the old blanket-empty stub encoded the swallow bug.

    Stubs subprocess so this file measures the promotion decision, not the linters
    (real binaries make it 214s; the integration suite covers the linting axis).
    """
    clean = {
        "pylint": "[]",
        "bandit": '{"results": [], "errors": []}',
        "semgrep": '{"results": [], "errors": []}',
    }

    def _stub(cmd, *_a, **_k):
        tool = cmd[0] if isinstance(cmd, (list, tuple)) and cmd else ""
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout=clean.get(tool, ""), stderr="",
        )

    with patch("subprocess.run", side_effect=_stub):
        yield


def test_the_matrix_covers_both_path_kinds():
    """🔴 공허화 차단 — 한쪽 종류만 있으면 아래 매트릭스가 비대칭을 못 본다."""
    kinds = {_is_test(p) for p in _PATHS}
    assert kinds == {True, False}, f"경로 집합이 한쪽으로 쏠렸다: {kinds}"
    assert _is_test("tests/conftest.py"), "디렉토리 규칙 표본이 사라졌다"
    assert not _is_test("src/testing_utils.py"), "경계 표본이 테스트로 분류됐다"


# ── 축 1: 전 바이너리 present → 경로 종류와 무관하게 정상 ──────────────────────


@pytest.mark.parametrize("path", _PATHS)
def test_all_binaries_present_never_marks_a_python_file_incomplete(path, no_subprocess):
    """🔴 `#1411` 직접 회귀 가드 — 조달이 멀쩡하면 **어떤 경로 종류도** incomplete 가 아니다.

    이 단언이 없던 동안 `#1410` 이 모든 테스트 파일을 incomplete 로 만들었고, 테스트를
    건드리는 PR 전부의 auto-merge 가 막혔다.

    ⚠️ **환경 의존 축이 섞여 있다** (Grok `01a0101a` 지적 — 정직 기준). `unavailable_tools`
    는 `shutil.which` 실측이라, 이 단언은 (a) 정책이 `is_enabled` 로 되돌아가도 red 지만
    (b) **바이너리가 없는 머신에서도** red 다. 후자는 로직 결함이 아니다.
    CI 는 `requirements.txt` 로 셋을 설치하므로 그 자리에서는 (a) 만 남는다
    (`test_static_incomplete.py` 가 이미 같은 함정을 적어 둔 축).
    Mixed axis: this also reddens on a machine missing the binaries, which is not a logic defect.
    """
    result = analyze_file(path, _CODE)
    assert result.incomplete is False, (
        f"{path}: 조달이 멀쩡한데 incomplete — 이 경로 종류의 PR 은 auto-merge 가 막힌다 "
        f"(unavailable={result.unavailable_tools})"
    )
    assert result.unavailable_tools == [], (
        f"{path}: 바이너리가 다 있는데 unavailable_tools={result.unavailable_tools}"
    )


# ── 축 2: 도구 부재 × 경로 종류 — 비대칭을 고정한다 ───────────────────────────


@pytest.mark.parametrize("tool", ["pylint", "flake8", "bandit"])
@pytest.mark.parametrize("path", _PATHS)
def test_provisioned_absence_promotes_except_where_the_tool_does_not_apply(
    tool, path, monkeypatch, no_subprocess,
):
    """조달 도구 부재는 incomplete — **단, 그 도구가 이 파일에 적용될 때만**.

    bandit 은 테스트 파일을 `supports()` 에서 제외하므로 부재해도 `unavailable_tools` 에
    들어가지 않는다. 그 사실을 승격 조건에 섞으면(`is_enabled` 로 옮기면) 모든 테스트
    파일이 배포 회귀로 오승격된다 — `#1411` 이 정확히 그 형태였다.
    """
    assert tool in PROVISIONED_ANALYZERS, f"{tool} 이 조달 계약에서 빠졌다 — 이 테스트가 공허하다"

    real = shutil.which
    monkeypatch.setattr(
        "shutil.which", lambda n, *a, **k: None if n == tool else real(n, *a, **k)
    )

    # 기대값은 `_tool_applies` 가 갖는다 — 그 docstring 이 왜 손유지인지 적는다.
    result = analyze_file(path, _CODE)

    assert (tool in result.unavailable_tools) is _tool_applies(tool, path), (
        f"{path} + {tool} 부재: unavailable_tools={result.unavailable_tools} "
        f"(적용 대상={_tool_applies(tool, path)})"
    )
    assert result.incomplete is _tool_applies(tool, path), (
        f"{path} + {tool} 부재 → incomplete={result.incomplete}, "
        f"기대={_tool_applies(tool, path)}. "
        "적용되지 않는 도구의 부재를 배포 회귀로 승격하면 그 경로 종류가 전부 막힌다."
    )


# ── 축 3: 실패 시점 × 경로 종류 — 타임아웃·crash 는 종류에 무관하다 ───────────


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("boom", [
    subprocess.TimeoutExpired(cmd="pylint", timeout=30),
    RuntimeError("도구가 내부에서 못 잡은 예외"),
], ids=["timeout", "crash"])
def test_failure_timing_promotes_regardless_of_path_kind(path, boom):
    """타임아웃·crash 는 **어떤 경로 종류에서도** incomplete 다 — fail-closed 대칭.

    두 경로가 갈리면 「테스트 파일은 타임아웃해도 통과」 같은 구멍이 생긴다.
    """
    with patch("subprocess.run", side_effect=boom):
        result = analyze_file(path, _CODE)
    assert result.incomplete is True, (
        f"{path}: 분석이 실패했는데 incomplete 가 아니다 — 미분석 코드가 만점으로 auto-merge 된다"
    )
