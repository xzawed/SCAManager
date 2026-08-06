"""e2e 공허화 차단 회귀 가드 — 두 경로(전건 skip · 범위 축소)를 함께 고정한다.

## 왜 (2026-08-06 5+1 회고 P1 · backlog R58)

e2e 초록에는 공허화 경로가 **둘** 있었다.

| 경로 | 증상 | 봉인 |
|---|---|---|
| `live_server` 가 `pytest.skip` | 앱이 부팅 못 해도 **121건 전건 skip → exit 0** | `RuntimeError` 로 전환 |
| 수집 건수 축소 | 테스트를 지우면 남은 것만 통과 | `scripts/check_e2e_scope.py` + `e2e/EXPECTED_COUNT` |

🔴 **실측**(뮤테이션): 봉인 전 서버 기동을 강제 실패시키면 `121 skipped … exit=0` 이었고,
봉인 후에는 `120 errors … exit=1` 이다.

이 리포는 같은 창에서 `lint-js`·의존성 핀·STATE 이력 절 **3 표면에 '범위 비면 fail'** 을
적용해 두고, **자기가 방금 초록으로 만든 e2e 에만** 적용하지 않았다 — 그 비대칭을 닫는다.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))  # _wiring_shape (배선 술어)

import check_e2e_scope  # noqa: E402


# ── ① 전건 skip 봉인 ────────────────────────────────────────────────────

def test_live_server_failure_raises_rather_than_skipping():
    """🔴 서버 기동 실패 경로가 `pytest.skip` 이면 안 된다 — skip 은 성공으로 집계된다.

    AST 로 본다: 산문 검색은 주석에 `pytest.skip` 이 있어도 걸리고, 반대로 표현이
    바뀌면 놓친다(양방향으로 틀린다).
    """
    tree = ast.parse((_ROOT / "e2e" / "conftest.py").read_text(encoding="utf-8"))
    fn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "live_server"),
        None,
    )
    assert fn is not None, "live_server 픽스처를 못 찾았다 — 이름이 바뀌었으면 가드도 갱신할 것"

    skips = [
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "skip"
        and isinstance(n.func.value, ast.Name) and n.func.value.id == "pytest"
    ]
    assert not skips, (
        "live_server 가 `pytest.skip` 을 호출한다 — 서버가 죽어도 전 스위트가 skip 되고 "
        "job 은 exit 0 이 된다(공허한 초록).\n→ 예외를 던져 **실패**시킬 것."
    )


def test_live_server_failure_path_raises():
    """대조군 — skip 이 없는 것만 보면 '실패 처리 자체가 사라진' 상태도 통과한다."""
    tree = ast.parse((_ROOT / "e2e" / "conftest.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "live_server")
    raises = [n for n in ast.walk(fn) if isinstance(n, ast.Raise)]
    assert raises, "live_server 에 실패 경로(raise)가 없다 — 기동 실패가 무시된다"


# ── ② 검사 범위 baseline ────────────────────────────────────────────────

def test_baseline_file_exists_and_is_an_integer():
    n = check_e2e_scope.read_baseline()
    assert isinstance(n, int) and n > 0, "e2e/EXPECTED_COUNT 가 양의 정수가 아니다"


def test_scope_guard_fails_closed_when_baseline_is_unreadable(tmp_path):
    """🔴 baseline 을 못 읽으면 **통과가 아니라 실패**여야 한다.

    없는 상태로 통과시키면 이 가드 자신이 공허해진다(빈 범위 위의 초록).
    """
    assert check_e2e_scope.read_baseline(tmp_path / "nope") is None


def test_scope_guard_fails_closed_when_collection_output_is_unparseable():
    """수집 출력이 이상하면 `None` — 호출부가 실패로 처리한다."""
    assert check_e2e_scope.parse_collected("") is None
    assert check_e2e_scope.parse_collected("ERROR: no tests ran") is None


def test_scope_guard_reads_the_last_collected_line():
    """🔴 **마지막** 매치를 써야 한다 — 앞부분은 nodeid 덤프라 첫 매치가 위험하다."""
    out = "e2e/test_a.py::t1\ne2e/test_a.py::t2\n\n3 tests collected in 0.01s\n"
    assert check_e2e_scope.parse_collected(out) == 3
    two = "9 tests collected in 0.01s\n\n121 tests collected in 0.04s\n"
    assert check_e2e_scope.parse_collected(two) == 121


def test_scope_guard_is_wired_into_ci():
    """정의 ≠ 배선 (3-불변식 ③) — CI 가 실제로 이 스크립트를 **실행**하는지.

    🔴 substring(`"...py" in ci`)은 금지다 — `echo 'scripts/check_e2e_scope.py'` 나
    주석만 있어도 통과한다(`guards.md` §배선 단언은 `_wiring_shape` 술어 의무).
    초판이 정확히 그 substring 이었고 Grok claim-review `71bd2d6c` 가 적발했다.
    """
    from _wiring_shape import surface_invokes

    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert surface_invokes(ci, "scripts/check_e2e_scope.py"), (
        "가드가 CI 에서 **실행**되지 않는다 — 문자열만 있고 호출이 없으면 dead code"
    )


def test_scope_guard_is_wired_into_the_local_runner():
    """`pre_push_gate` 러너에도 있어야 한다 — CI 와 갈라지면 '로컬 초록' 이 무의미하다."""
    runner = (_ROOT / "scripts" / "pre_push_gate.py").read_text(encoding="utf-8")
    assert "check_e2e_scope.py" in runner, (
        "러너 목록에 없다 — CI 는 돌리는데 로컬은 안 돌려서 push 전 확인이 거짓이 된다"
    )


def test_min_passed_gate_is_wired_into_ci():
    """🔴 **전건 skip 은 수집 baseline 으로 못 잡는다** — 통과 하한이 그 유일한 관측면.

    실측: 121건을 전부 skip 시키면 baseline 가드는 통과하고(수집 121 유지) pytest 는
    exit 0 이다. `--e2e-min-passed` 가 있어야 red 가 된다.
    """
    ci = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "--e2e-min-passed=" in ci, "e2e 실행에 통과 건수 하한이 없다 — 전건 skip 이 초록"


def test_min_passed_option_exists_in_conftest():
    """옵션이 실제로 정의돼 있어야 CI 인자가 의미를 갖는다(정의 ≠ 사용의 역방향)."""
    conftest = (_ROOT / "e2e" / "conftest.py").read_text(encoding="utf-8")
    tree = ast.parse(conftest)
    names = {n.name for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert "pytest_addoption" in names, "--e2e-min-passed 옵션 정의가 없다"
    assert "pytest_sessionfinish" in names, "하한을 판정하는 훅이 없다"
