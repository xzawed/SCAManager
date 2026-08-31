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


def _live_server_fn():
    tree = ast.parse((_ROOT / "e2e" / "conftest.py").read_text(encoding="utf-8"))
    return next(n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "live_server")


def test_health_poll_does_not_swallow_the_reason():
    """🔴 폴링 예외를 `pass` 로 버리면 실패가 **읽을 수 없게** 된다 (CodeQL `py/empty-except`).

    R58 이 skip 을 실패로 바꾼 목적은 실패를 **관측 가능**하게 하는 것이다. 그런데
    "60회 시도했지만 응답 없음" 만 남기고 *왜*(연결 거부 / 500 / 타임아웃)를 버리면
    절반만 이행한 것이다 — 운영자·CI 로그를 보는 사람은 여전히 원인을 모른다.
    """
    empty = [
        h for h in ast.walk(_live_server_fn())
        if isinstance(h, ast.ExceptHandler)
        and all(isinstance(st, ast.Pass) for st in h.body)
    ]
    assert not empty, (
        "live_server 의 except 블록이 `pass` 뿐이다 — 실패 이유가 버려진다.\n"
        "→ 마지막 오류를 남겨 `RuntimeError` 메시지에 실을 것."
    )


def test_startup_failure_message_carries_the_last_error():
    """대조군 — 오류를 **잡아만 두고 쓰지 않으면** 위 단언은 통과하지만 여전히 안 보인다."""
    names = {
        node.id
        for raise_node in ast.walk(_live_server_fn()) if isinstance(raise_node, ast.Raise)
        for node in ast.walk(raise_node) if isinstance(node, ast.Name)
    }
    assert "last_error" in names, (
        "기동 실패 메시지가 마지막 오류를 싣지 않는다 — 잡아 두고 버리는 것과 같다"
    )


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


# ── ③ 세 번째 공허화 경로: 무조건 skip (#1587) ────────────────────────────────
#
# 🔴 위 두 봉인은 「전건 skip」과 「범위 축소」를 막지만, **개별 시험 하나가 무조건 skip**
#    되는 것은 둘 다 통과한다(실측): `e2e/EXPECTED_COUNT` 는 **수집** 건수라 skip 도 세고,
#    `--e2e-min-passed=100` 은 122-1=121 이라 하한에 걸리지 않는다.
#    그 시험은 로컬·CI 어디서도 실행된 적이 없고, 재활성화가 사람 기억에만 달려 있다.
#
# 🔴 개수를 못박지 않는다 — 「무조건 skip 이 있으면 red」라는 **형태 판정**이다.
#    개수 스냅샷은 정당한 시험 추가를 벌한다.
#    허용: 조건이 **상수가 아닌** `skipif`, 그리고 함수 본문의 `pytest.skip(...)` —
#    둘 다 조건이 참이 되면 스스로 깨어난다.
# The third emptiness path: one unconditionally-skipped test passes both existing seals.

_SKIP_ATTRS = ("skip", "skipif")


def _mark_tail(node: ast.AST) -> str | None:
    """마커 표현식의 끝 속성 이름 — `pytest.mark.skip(...)` → `"skip"`."""
    target = node.func if isinstance(node, ast.Call) else node
    return target.attr if isinstance(target, ast.Attribute) else None


def _never_wakes(node: ast.AST, aliases: set[str]) -> bool:
    """이 마커가 **결코 깨어나지 않는가** — 무조건 skip 이거나 상수 참 `skipif` 인가.

    🔴 이름을 푼다. `_SKIP = pytest.mark.skip(...)` 뒤 `@_SKIP` 은 데코레이터가 `Name` 이라
    속성만 보면 통째로 눈먼다 — 그런데 그것이 **이 리포의 집 스타일**이다
    (`@_requires_postgres` · `@pytestmark_semver` · `@_SKIP`, 전부 실재).
    🔴 `skipif(True, …)` 도 잡는다 — 형태만 조건부이고 사실은 무조건이다.
    조건이 상수가 아니면(`shutil.which(...) is None` 등) 깨어날 수 있으므로 허용한다.
    Resolve names: the repo's own idiom puts the marker in a module-level constant.
    """
    if isinstance(node, ast.Name):
        return node.id in aliases
    tail = _mark_tail(node)
    if tail == "skip":
        return True
    if tail == "skipif" and isinstance(node, ast.Call) and node.args:
        cond = node.args[0]
        return isinstance(cond, ast.Constant) and bool(cond.value)
    return False


def _skip_aliases(tree: ast.AST) -> set[str]:
    """모듈 최상위에서 「결코 깨어나지 않는」 마커를 담은 이름들."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if _mark_tail(node.value) in _SKIP_ATTRS and _never_wakes(node.value, set()):
            out.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return out


def _flatten(node: ast.AST):
    """리스트/튜플이면 원소를, 아니면 자신을 낸다 — `pytestmark = [mark]` 도 유효하다."""
    if isinstance(node, (ast.List, ast.Tuple)):
        yield from node.elts
    else:
        yield node


def _unconditional_skips(root: Path) -> list[str]:
    """결코 실행되지 않는 시험을 만드는 자리들 — 적용 지점 넷을 모두 본다.

    데코레이터 · `pytestmark` · `pytest.param(marks=…)` · `add_marker`/`applymarker`.
    (Grok claim-review `01a05661` 이 앞의 셋을 구멍으로 짚었다.)
    """
    def _label(path: Path) -> str:
        # 자기검사는 `tmp_path` 를 쓰므로 리포 밖 경로가 온다 — 그때는 그대로 적는다.
        try:
            return path.relative_to(_ROOT).as_posix()
        except ValueError:
            return path.as_posix()

    out: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = _skip_aliases(tree)

        def _flag(node, where, *, p=path, a=aliases, o=out):
            for item in _flatten(node):
                if _never_wakes(item, a):
                    o.append(f"{_label(p)}:{item.lineno} ({where})")

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in node.decorator_list:
                    _flag(dec, node.name)
            elif isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets):
                _flag(node.value, "pytestmark")
            elif isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg == "marks":
                        _flag(kw.value, "marks=")
                if _mark_tail(node) in ("add_marker", "applymarker"):
                    for arg in node.args:
                        _flag(arg, "add_marker")
    return out


_PROBE = '''import pytest

pytestmark = [pytest.mark.skip(reason="리스트 pytestmark 도 유효하다")]

_ALIAS = pytest.mark.skip(reason="집 스타일 — 마커를 이름에 담는다")
_OK_ALIAS = pytest.mark.skipif(SOME_RUNTIME_CONDITION, reason="깨어날 수 있다")


@pytest.mark.skip(reason="직접")
def test_a():
    pass


@_ALIAS
def test_b():
    pass


@pytest.mark.skipif(True, reason="형태만 조건부")
def test_c():
    pass


@_OK_ALIAS
def test_d():
    pass


@pytest.mark.skipif(SOME_RUNTIME_CONDITION, reason="허용")
def test_e():
    pass
'''


def test_the_skip_detector_is_not_vacuous(tmp_path):
    """🔴 탐지기가 0건만 낼 줄 알면 아래 단언이 공허하다 — 네 모양을 심어 잡히는지 본다.

    심는 것: 직접 데코레이터 · **별칭**(집 스타일) · 상수 참 `skipif` · 리스트 `pytestmark`.
    안 잡혀야 하는 것: 조건이 상수가 아닌 `skipif` 두 건(직접·별칭).
    """
    (tmp_path / "probe.py").write_text(_PROBE, encoding="utf-8")
    found = _unconditional_skips(tmp_path)
    where = sorted(f.split("(")[-1].rstrip(")") for f in found)
    assert where == ["pytestmark", "test_a", "test_b", "test_c"], (
        f"네 모양을 정확히 잡아야 하고 깨어날 수 있는 skipif 는 잡으면 안 된다: {found}"
    )


def test_no_test_is_unconditionally_skipped():
    """🔴 무조건 skip 은 **한 번도 실행되지 않는 시험**이고 두 봉인을 다 빠져나간다.

    조건부로 바꿔라 — 재활성화 조건을 산문이 아니라 코드에 적으면 조건이 참이 되는 순간
    스스로 깨어난다. 정말 필요 없어진 시험이면 지우고 `e2e/EXPECTED_COUNT` 를 맞춰라.
    """
    offenders = _unconditional_skips(_ROOT / "tests") + _unconditional_skips(_ROOT / "e2e")
    assert not offenders, (
        f"결코 실행되지 않는 시험 {len(offenders)}건: {offenders}\n"
        "  `e2e/EXPECTED_COUNT`(수집 건수)도 `--e2e-min-passed`(하한)도 이것을 못 잡는다.\n"
        "  런타임 조건부(`pytest.skip(...)` in body) 또는 상수 아닌 `skipif` 로 바꾸거나, 지워라."
    )
