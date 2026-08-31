"""분석기 어댑터의 fail-open 재고 — 새로 늘지 않게 못 박는다 (감사 A2 확장, #1519 / #1521).

`static.py::_run_analyzers` 의 계약: `run()` 이 **예외를 올릴 때만** `incomplete` 로 승격한다.
`[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.

## 🔴 이 파일의 이전 판은 거짓 집행자였다 (실측)

이전 탐지기는 **관용구 두 개**만 알았다 — `startswith` 판정의 `return []` 과
`JSONDecodeError` 핸들러의 `return []`. 관용구 열거는 열거하지 않은 형태에 원리적으로 눈먼다:

    리포에 실재하는 fail-open 형태 7종 중  탐지 2종 · 눈먼 것 5종
    뮤테이션: 눈먼 형태로 새 어댑터 2개 투입 → 가드 exit 0 (5 passed)

그래서 `KNOWN_FAIL_OPEN` 에 적혀 있던 14개는 **실제 집합이 아니라 눈먼 탐지기의 출력**이었다.
재집계 20 → W1 5개(관측면 0)·W3 3개(스폰 축)·W2 5개(실측 판별식)를 fail-closed 로 돌려
현재 **6개**다. 형태 7종은 `tests/unit/analyzer/fixtures/` 에 픽스처로 박혀 있고,
각 파일 docstring 이 그 형태를 쓰는 실물 어댑터 좌표를 든다.

## 판정을 관용구에서 파생값으로 바꿨다

`[]` 가 정당한 자리는 **두 축뿐**이고, 둘 다 다른 기전이 이미 담당한다:

    except subprocess.TimeoutExpired → `ctx.timed_out` 이 incomplete 로 승격한다
    except FileNotFoundError         → 조달 축(`unavailable_tools`)이 담당한다

그 밖의 `[]` 는 전부 「분석 못 했는데 깨끗하다고 보고」다. 그래서 판정은 열거가 아니라 파생이다:

    A. 모듈 안 어느 함수에도 `raise` 가 없다      → 크래시 판별식이 아예 없다
    B. 위 두 축 밖의 `return []` 이 하나라도 있다  → 그 자리가 미분석을 삼킨다
    D. `except` 밖에 `if …: raise` 가 없다        → 장식용 raise 만 있다

축 D 는 축 A 의 사각을 닫는다. `except` 갈래의 `raise` 하나면 A 가 꺼지는데, 그것이 잡는 것은
「파싱이 예외를 냈다」뿐이다. 크래시 stdout 이 깨끗한 것과 **바이트가 같으면**(shellcheck 의 `[]`)
파싱은 성공하고 0건이 «완전» 으로 기록된다 — #1582 가 실측으로 닫은 자리가 정확히 그것이다.
그 한 줄을 지우는 뮤테이션에 이전 판은 눈멀었다: fail-closed 17개 중 **13개**가 A·B·C 를
전부 빠져나갔고, 그 안에 이 파일 자신의 경성 대조군 `semgrep` 이 있었다(#1585).

위 축들 모두 **모듈의 모든 함수**를 본다. 「`run` 과 `_parse*` 만」처럼 이름으로 범위를
정하면 다르게 명명된 헬퍼에 눈멀고, 그것은 관용구 열거와 같은 실패다.

`except OSError` 는 B 로 걸린다 — `shutil.which` 를 통과한 뒤의 ENOEXEC(깨진 shebang)·
PermissionError·TOCTOU 는 「바이너리 부재」가 아니라 미분석이다. 이 구별은 `FileNotFoundError`
로 좁힌 어댑터만 갖는다(실측 10/23). 어느 것이 남았는지는 이 파일이 아니라 **탐지기**가
말한다 — 아래 목록은 그 출력과 대조될 뿐이고, 목록을 손으로 읽어 판단하지 않는다.

## 이 파일이 하는 것

1. 현재 fail-open 인 어댑터 집합을 명시한다. 목록 밖 어댑터가 fail-open 이면 **red**.
2. 목록이 **비면 red** — 부채가 사라졌으니 이 파일을 지우라는 신호다.
3. 탐지기가 다시 눈멀면 **red** — 픽스처를 전부 봐야 한다.

The debt is inventoried, not hidden: the set may shrink but never grow, and the detector is
derived from the two legitimate axes rather than from a list of idioms it might fail to list.
"""
from __future__ import annotations

import ast
import io
from pathlib import Path

_TOOLS = Path("src/analyzer/io/tools")
_SHAPES_FAIL_OPEN = Path("tests/unit/analyzer/fixtures/failopen_shapes")
_SHAPES_FAIL_CLOSED = Path("tests/unit/analyzer/fixtures/failclosed_shapes")

# `[]` 가 정당한 두 축 — 다른 기전이 이미 담당한다(모듈 docstring 참조).
# The two axes where an empty return is legitimate; other mechanisms own them.
_NARROW_AXES = ("TimeoutExpired", "FileNotFoundError")

# 🔴 현재 fail-open 인 어댑터 — **줄이기만 한다.** 새 이름을 여기 넣지 마라.
# 고친 어댑터는 이 목록에서 빼면 된다.
KNOWN_FAIL_OPEN: frozenset[str] = frozenset({
    # 분석 축이 통째로 fail-open — 크래시가 «이슈 0건 · 완전» 이 된다.
    # 남은 6개는 #1557 W2 잔여다: semgrep 이 같은 언어를 덮지만 **전담 축은 사라진다**.
    # 그중 배포본에서 실제로 도는 것은 **2개**(golangci_lint · ktlint) —
    # `_REACHABLE_CEILING` 이 그 수를 파생값으로 래칫한다.
    # 🔴 판별식은 도구마다 다르다 — 실측으로 정한 것만 전환한다. rubocop 은 크래시해도
    #    유효한 JSON 을 내므로 「비-JSON 이면 raise」 관용구가 통하지 않았다.
    "dotnet_format", "golangci_lint", "htmlhint", "ktlint",
    "phpstan", "swiftlint",
})


def _analysis_functions(tree: ast.AST) -> list[ast.FunctionDef]:
    """어댑터 모듈의 **모든** 함수.

    🔴 범위를 이름으로 정하지 않는다(`run`·`_parse*` 열거). 그렇게 하면 다르게 명명된
    헬퍼(`ktlint.py::json_array_payload` 같은)에 fail-open 을 두는 순간 눈먼다 —
    **관용구 열거와 같은 클래스의 결함**이고, 이 파일은 바로 그것을 고치려고 다시 쓰였다.
    실측(2026-08-26): 범위 밖 함수에 `return []` 은 현재 0건이므로 넓혀도 판정은 안 바뀐다.
    Do not scope by function name: that is the same failure class as enumerating idioms.
    """
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


def _empty_return_guards(fn: ast.FunctionDef) -> list[tuple[int, str]]:
    """`return []` 마다 `(줄번호, 그것을 감싼 except 절)` 을 낸다.

    except 안이 아니면 `"<no except>"` — 판정문에서 곧바로 빈 결과를 낸 자리다.
    """
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            parent[child] = node
    out: list[tuple[int, str]] = []
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Return)
                and isinstance(node.value, ast.List) and not node.value.elts):
            continue
        cur: ast.AST = node
        guard = "<no except>"
        while cur in parent:
            up = parent[cur]
            if isinstance(up, ast.ExceptHandler):
                guard = ast.unparse(up.type) if up.type is not None else "<bare except>"
                break
            cur = up
        out.append((node.lineno, guard))
    return out



def _swallows_without_raising(handler: ast.ExceptHandler) -> bool:
    """이 `except` 가 **아무것도 올리지 않고** 흐름만 이어가는가 (`continue`/`pass`/`return None`)."""
    if any(isinstance(n, ast.Raise) for n in ast.walk(handler)):
        return False
    return any(
        isinstance(n, (ast.Continue, ast.Pass))
        or (isinstance(n, ast.Return)
            and (n.value is None
                 or (isinstance(n.value, ast.Constant) and n.value.value is None)))
        for n in ast.walk(handler)
    )


def _accumulating_loops(tree: ast.AST) -> list[ast.For | ast.While]:
    """이슈를 모으는 루프들 — `for`/`while` 안에 `.append(...)` 가 있는 것."""
    return [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.For, ast.While))
        and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
                and c.func.attr == "append" for c in ast.walk(node))
    ]


def _names_the_loop_writes(loops: list[ast.For | ast.While]) -> set[str]:
    """누산 루프가 **실제로 쓰는** 이름들 — 대입 대상과 `.append` 수신자.

    이 집합이 완화 판정의 정의역이다. 무관한 `if not <아무 이름>: raise` 하나로 축이
    꺼지지 않게 한다 — 그러면 그 어댑터의 침묵이 통째로 투명해진다.
    Names the accumulating loop actually writes: assignment targets and `.append` receivers.
    """
    names: set[str] = set()
    for loop in loops:
        for n in ast.walk(loop):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
                names.add(n.id)
            elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "append" and isinstance(n.func.value, ast.Name)):
                names.add(n.func.value.id)
    return names


def _functions_the_loop_calls(loops: list[ast.For | ast.While]) -> set[str]:
    """누산 루프가 부르는 함수 이름들 — 삼킴이 **그 루프를 먹이는지** 판정하는 정의역."""
    names: set[str] = set()
    for loop in loops:
        for n in ast.walk(loop):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Name):
                    names.add(n.func.id)
                elif isinstance(n.func, ast.Attribute):
                    names.add(n.func.attr)
    return names


def _swallow_feeds_the_loop(tree: ast.AST, loops: list[ast.For | ast.While]) -> bool:
    """삼키는 `except` 가 **그 누산 루프를 먹이는가** — 루프 안이거나, 루프가 부르는 함수 안.

    🔴 모듈 어딘가의 `except: pass` 를 세면 안 된다. 정리 코드의 무관한 삼킴 하나로
    fail-closed 어댑터가 결함으로 잡히고, 거짓 양성이 나오면 사람이 가드를 끈다.
    🔴 「루프 안」만 봐도 안 된다 — 실물 형태는 헬퍼 급여다
    (`clippy.py::def _parse_clippy_line(line: str, ctx: AnalyzeContext) -> AnalysisIssue | None:`).
    Does the swallow actually feed the accumulator: inside the loop, or inside a callee of it.
    """
    def _swallows(scope: ast.AST) -> bool:
        return any(_swallows_without_raising(h)
                   for n in ast.walk(scope) if isinstance(n, ast.Try) for h in n.handlers)

    if any(_swallows(loop) for loop in loops):
        return True
    called = _functions_the_loop_calls(loops)
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in called and _swallows(node)
        for node in ast.walk(tree)
    )


def _raises_on_empty_accumulator(tree: ast.AST, written: set[str]) -> bool:
    """읽은 것이 0건일 때 올리는 자리가 있는가 — 이 형태의 **완화**다.

    `python.py::            if not issues and r.returncode != 0:` 가 그 예다.
    공용 헬퍼 `empty_output_is_a_crash` 를 부르는 것도 같은 완화다.

    🔴 `written` 은 누산 루프가 실제로 쓰는 이름들이다. 그 밖의 이름에 걸린 `raise` 는
    이 형태의 완화가 아니다 — 정의역을 좁히지 않으면 무관한 가드 하나가 축 C 를 끈다.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)                 and node.func.id == "empty_output_is_a_crash":
            return True
        # 🔴 이름이 아니라 **구조**로 본다 — `if not <지역이름>: … raise`.
        #    첫 판은 식별자 `issues` 를 찾았고, 누산 여부를 `parsed_any` 같은 다른 이름으로
        #    추적하는 어댑터를 놓쳤다(실측: clippy 를 고쳤는데도 계속 잡혔다).
        #    부분문자열이 상태를 대신하지 않게 한다.
        # Structure, not identifier: `if not <local>: … raise` is the mitigation shape.
        if isinstance(node, ast.If) and any(isinstance(n, ast.Raise) for n in ast.walk(node)):
            if any(isinstance(t, ast.UnaryOp) and isinstance(t.op, ast.Not)
                   and isinstance(t.operand, ast.Name) and t.operand.id in written
                   for t in ast.walk(node.test)):
                return True
    return False


def _has_crash_predicate(tree: ast.AST) -> bool:
    """도구가 **기대한 형식의 출력을 냈는가**를 보고 올리는 자리가 있는가.

    🔴 `except` 갈래 **안**의 `raise` 는 세지 않는다. 그것이 잡는 것은 「파싱이 예외를 냈다」
    뿐이고, 「도구가 조용히 죽어 깨끗한 것과 바이트가 같은 출력을 냈다」는 못 잡는다.
    후자를 잡는 것이 크래시 판별식이고, `#1581`·`#1582` 가 도구마다 실측으로 정한 것이
    바로 그 한 줄이다(`_common.py::def empty_output_is_a_crash` · `eslint.py` 의 컨테이너 검사).

    🔴 판별식의 **내용**을 규정하지 않는다 — 형태만 본다(`except` 밖의 `if …: raise`).
    내용을 규정하면 도구마다 다른 판별식을 열거하게 되고, 그것이 이 파일의 이전 판을
    거짓 집행자로 만든 관용구 열거와 같은 실패다. 「그 판별식이 실제로 크래시를 잡는가」는
    CI 실바이너리(`tests/integration/test_contracted_analyzers_real_binary.py` 의 `W2-SHAPE`)가
    잰다 — 로컬에 바이너리가 없는 여기서 의미를 판정하면 그것이 또 하나의 거짓 집행자다.

    Shape only, not content: an `if …: raise` outside any except handler. What that predicate
    actually catches is measured against real binaries in CI, not asserted here.
    """
    inside_except: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            inside_except.update(id(n) for n in ast.walk(node))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "empty_output_is_a_crash"):
            return True
        if (isinstance(node, ast.If) and id(node) not in inside_except
                and any(isinstance(n, ast.Raise) for n in ast.walk(node))):
            return True
    return False


def _fail_open_reasons(path: Path) -> list[str]:
    """어댑터 한 개가 fail-open 인 사유들. 빈 리스트면 fail-closed 다."""
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    fns = _analysis_functions(tree)
    reasons: list[str] = []
    if fns and not any(isinstance(n, ast.Raise) for fn in fns for n in ast.walk(fn)):
        reasons.append("A: 모듈 안 어느 함수에도 raise 가 없다 — 크래시 판별식 자체가 없다")
    for fn in fns:
        for lineno, guard in _empty_return_guards(fn):
            if not any(axis in guard for axis in _NARROW_AXES):
                reasons.append(f"B: L{lineno} `return []` under `{guard}`")
    # 🔴 축 C — **조용한 누산기.** 이슈를 모으는 루프 안에서 파싱 실패를 삼키고, 읽은 것이
    #    0건이어도 그대로 내보내는 형태다. `return []` 을 쓰지 않으므로 **B 가 못 본다.**
    #    그리고 모듈이 다른 이유로 `raise` 를 하나 얻으면 **A 도 꺼진다** — 그때 이 형태는
    #    통째로 투명해진다. `ba1e0955` 가 clippy 에서 정확히 그렇게 했다(실측).
    #
    #    🔴 컷: 루프 뒤에 「읽은 것이 0건이면 올린다」가 있으면 **완화된 것**이라 잡지 않는다.
    #    그 컷이 없으면 `python.py`(pylint·flake8·bandit — 전부 조달됨)가 잡혀 잔여 집합이
    #    5에서 8로 뛴다. 완화를 결함으로 세는 것은 거짓 양성이고, 그러면 사람이 가드를 끈다.
    # Axis C: a parse failure swallowed inside an accumulating loop, with no raise-on-empty
    # afterwards. B cannot see it (no `return []`) and A goes dark once any raise exists.
    loops = _accumulating_loops(tree)
    if (loops
            and _swallow_feeds_the_loop(tree, loops)
            and not _raises_on_empty_accumulator(tree, _names_the_loop_writes(loops))):
        reasons.append(
            "C: 누산 루프 안에서 파싱 실패를 삼키고, 읽은 것이 0건이어도 그대로 내보낸다"
        )
    # 🔴 축 D — **장식용 raise.** `except` 갈래의 raise 하나가 축 A 를 끄지만, 그것은
    #    「파싱이 예외를 냈다」만 잡는다. 크래시 stdout 이 깨끗한 것과 바이트가 같으면
    #    (shellcheck 의 `[]`) 파싱은 성공하고 0건이 «완전» 으로 기록된다.
    #
    #    🔴 이 축이 없으면 이 파일은 **자기가 세운 축이 되돌아가는 것을 못 본다.**
    #    뮤테이션 실측(`0017a3eb`): `except` 밖의 `if …: raise` 를 지우면 fail-closed 17개 중
    #    **13개**가 A·B·C 를 전부 빠져나갔다 — 경성 대조군 `semgrep` 을 포함해서다.
    #    #1581·#1582 가 도구별 실측으로 세운 판별식을 지우는 것이 그 뮤테이션이므로,
    #    이 축은 전환된 어댑터를 지키는 래칫이다.
    # Axis D: a decorative raise in an except handler turns axis A off while catching only
    # "the parse threw" — never "the tool died and emitted bytes identical to clean".
    if fns and not _has_crash_predicate(tree):
        reasons.append(
            "D: 크래시 판별식이 없다 — raise 는 except 갈래에만 있어 "
            "「파싱이 예외를 냈다」만 잡고 조용한 크래시는 못 잡는다"
        )
    return reasons


def _fail_open_adapters(root: Path = _TOOLS) -> set[str]:
    """분석 실패를 `[]` 로 삼키는 어댑터 이름 — 판정은 모듈 docstring 의 A·B·C·D 축."""
    return {
        path.stem for path in sorted(root.glob("*.py"))
        if not path.name.startswith("_") and path.name != "__init__.py"
        and _fail_open_reasons(path)
    }


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_detector_actually_finds_something():
    """🔴 탐지기가 0건을 내면 이 파일 전체가 공허하다."""
    assert _fail_open_adapters(), (
        "fail-open 어댑터를 하나도 못 찾았다 — AST 탐지기가 깨졌거나 "
        "어댑터 구조가 바뀌었다. 목록이 진짜 비었다면 이 파일을 지워라."
    )


def test_a_hardened_adapter_is_not_flagged():
    """🔴 대조군 — 두 축으로만 `[]` 를 내는 `semgrep`·`python` 은 잡히면 안 된다.

    잡힌다면 탐지기가 「타임아웃·조달」과 「미분석」을 구분하지 못하는 것이다.
    """
    for hardened in ("semgrep", "python"):
        reasons = _fail_open_reasons(_TOOLS / f"{hardened}.py")
        assert not reasons, (
            f"{hardened} 이 fail-open 으로 잡혔다 — 수정이 되돌아갔거나 탐지기가 틀렸다: {reasons}"
        )


# ─── 탐지기 실명 회귀 — 실재하는 형태를 픽스처로 박아 둔다 ───────────────────


def test_detector_sees_every_fail_open_shape_that_exists_in_tree():
    """🔴 탐지기가 **실재하는** fail-open 형태를 전부 봐야 한다.

    각 픽스처는 리포 안의 실물에서 뜬 것이다(파일 docstring 에 실물 좌표가 있다).
    관용구를 열거하는 탐지기는 열거하지 않은 형태에 원리적으로 눈먼다 — 그 눈멂이
    「fail-open 은 늘지 않는다」를 거짓 초록으로 만든다(이전 판이 그랬다, 뮤테이션 실측).
    """
    present = {p.stem for p in _SHAPES_FAIL_OPEN.glob("*.py")}
    assert present, "픽스처가 사라졌다 — 이 테스트가 공허해졌다"
    missed = sorted(present - _fail_open_adapters(_SHAPES_FAIL_OPEN))
    assert not missed, (
        f"탐지기가 {len(missed)}/{len(present)} 형태에 눈멀었다: {missed}. "
        "각 픽스처 파일의 docstring 에 이 형태를 쓰는 실물 어댑터 좌표가 있다."
    )


def test_detector_does_not_flag_the_narrow_axes():
    """🔴 음성 대조 — 두 축으로만 `[]` 를 내고 분석 실패는 raise 하는 어댑터.

    이것이 잡히면 재고가 영원히 비지 않아 부채가 사라졌는지 알 수 없게 된다.
    """
    flagged = sorted(_fail_open_adapters(_SHAPES_FAIL_CLOSED))
    assert not flagged, (
        f"fail-closed 어댑터가 잡혔다: {flagged} — 탐지기가 축을 구별하지 못한다"
    )


# ─── 재고 ────────────────────────────────────────────────────────────────────


def test_fail_open_set_does_not_grow():
    """🔴 fail-open 어댑터가 **늘지 않는다** — 새 어댑터는 fail-closed 로 써라.

    늘면 그만큼 언어가 조용히 미분석 상태로 만점을 받게 된다.
    """
    new = sorted(_fail_open_adapters() - KNOWN_FAIL_OPEN)
    detail = {n: _fail_open_reasons(_TOOLS / f"{n}.py") for n in new}
    assert not new, (
        f"fail-open 어댑터가 늘었다: {detail}. 분석 실패는 `raise` 로 올려라 — "
        "`[]` 는 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다. "
        "본보기: src/analyzer/io/tools/semgrep.py::_fail"
    )


def test_the_known_list_has_no_stale_names():
    """고쳐 놓고 목록에서 안 뺀 이름은 다음 사람에게 거짓 부채를 보여준다."""
    stale = sorted(KNOWN_FAIL_OPEN - _fail_open_adapters())
    assert not stale, (
        f"{stale} 는 이미 fail-closed 인데 KNOWN_FAIL_OPEN 에 남아 있다 — 목록에서 빼라"
    )


def test_delete_this_file_when_the_list_empties():
    """목록이 비면 red — 부채가 사라졌으니 이 파일도 지우라는 신호다."""
    assert KNOWN_FAIL_OPEN, (
        "KNOWN_FAIL_OPEN 이 비었다 — 모든 어댑터가 fail-closed 다. "
        "이 파일을 지우고 `test_fail_open_set_does_not_grow` 를 "
        "「fail-open 어댑터는 0개다」 단언으로 바꿔라."
    )


# ── 잔여 부채 중 **배포본에서 실제로 도는 것** (회고 2026-08-29 P1) ─────────────
#
# 🔴 사고: 이 사이클이 닫은 11개 중 **5개는 배포 이미지에서 실행조차 되지 않았다**
#    (buf_lint · clippy · dart_analyze · psscriptanalyzer · stylelint). 반대로 잔여 6개 중
#    2개는 **돈다**(cppcheck·hadolint·shellcheck 는 #1557 W2 로 전환됐다). 투입의 약 45%가 도달 불가능한 위험에 갔고, 그동안 C/C++·Go·
#    Dockerfile·Kotlin·shell 파일이 크래시를 «이슈 0건 · 완전» 으로 기록하는 경로는 그대로였다.
#    우선순위를 조달과 대조한 적이 한 번도 없었기 때문이다.
#
# 이 가드는 그 대조를 **파생값**으로 만든다. 손으로 적은 두 번째 목록을 두지 않는다 —
# 그러면 세 번째 SSOT 가 되고, 그 목록이 늙는 순간 이 가드가 거짓을 보증한다.
#
# 🔴 조인을 **등록명**(`name = "..."`)으로 한다. 파일 stem 으로 교집합을 내면
#    `golangci_lint.py` 가 등록하는 `"golangci-lint"` 를 **조용히 떨어뜨려** 5를 4로 만든다
#    (실측). 그것이 바로 이 리포가 반복해 온 거짓 집행자다. 두 조인이 어긋나면 red 다.

_REACHABLE_CEILING = 2
"""잔여 fail-open ∩ 조달의 상한 — **파생 개수**의 래칫이지 손으로 적은 목록이 아니다.

부채를 닫아 줄면 같은 PR 에서 이 수를 내린다. 늘어나면 red — 새로 조달한 도구가
이미 fail-open 이라는 뜻이고, 그것이 다음 W 패키지의 선별 입력이다.
"""


def _registered_names(stem: str) -> set[str]:
    """어댑터 파일이 **실제로 등록하는 이름** — stem 추측이 아니라 AST 로 읽는다."""
    tree = ast.parse((_TOOLS / f"{stem}.py").read_text(encoding="utf-8"))
    return {
        st.value.value
        for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
        for st in node.body
        if isinstance(st, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "name" for t in st.targets)
        and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str)
    }


def test_reachable_fail_open_does_not_grow():
    """🔴 배포본에서 **실제로 도는** 잔여 fail-open 이 늘면 red.

    세 축을 함께 단언한다 — 하나만 두면 조인이 눈멀어도 초록이 된다.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS  # noqa: PLC0415

    stems = sorted(_fail_open_adapters())

    unmapped = [s for s in stems if not _registered_names(s)]
    assert not unmapped, (
        f"등록명을 못 읽은 어댑터: {unmapped} — 조인이 그만큼 눈먼다"
    )

    by_name = {n for s in stems for n in _registered_names(s)}
    live = sorted(by_name & PROVISIONED_ANALYZERS)
    by_hyphen = sorted({s.replace("_", "-") for s in stems} & PROVISIONED_ANALYZERS)

    assert by_hyphen == live, (
        f"🔴 두 조인이 어긋난다 — hyphen={by_hyphen} name={live}. "
        "어느 한쪽이 조용히 떨어뜨리고 있다는 뜻이므로 개수를 믿으면 안 된다."
    )
    assert live, (
        "도달 가능한 fail-open 이 0건 — 조인이 눈멀었거나 부채가 사라졌다. "
        "후자면 이 테스트를 지워라(위 `test_delete_this_file_when_the_list_empties` 와 같은 신호)."
    )
    # 🔴 상한 자체를 파생값으로 묶는다 — 안 묶으면 이 래칫은 상한을 올리는 것만으로
    #    조용히 꺼진다(뮤테이션 실측: 999 로 바꿔도 초록이었다). 조달된 도구 수보다 많은
    #    「도달 가능한 fail-open」은 존재할 수 없으므로 그것이 자연스러운 천장이다.
    #    부채를 닫아 줄일 때는 이 단언이 막지 않는다(위로만 묶는다).
    # Bound the ceiling itself: otherwise raising it silently disarms the ratchet.
    assert _REACHABLE_CEILING <= len(PROVISIONED_ANALYZERS), (
        f"상한 {_REACHABLE_CEILING} 이 조달 도구 수 "
        f"{len(PROVISIONED_ANALYZERS)} 를 넘는다 — "
        "그 값으로는 아무것도 막지 못한다."
    )
    assert len(live) <= _REACHABLE_CEILING, (
        f"🔴 배포본에서 도는 fail-open 이 {len(live)}개로 늘었다: {live}\n"
        f"   (상한 {_REACHABLE_CEILING}) — 새로 조달한 도구가 이미 fail-open 이다.\n"
        "   이 목록이 다음 W 패키지의 선별 입력이다. `LIVE_FAIL_OPEN` 같은 두 번째 목록을\n"
        "   만들지 마라 — 세 번째 SSOT 가 되고 그것이 늙으면 이 가드가 거짓을 보증한다."
    )


def test_the_naive_stem_join_would_undercount():
    """🔴 계기 자기검사 — stem 교집합이 실제로 떨어뜨리는지 확인한다.

    이 단언이 없으면 위 `by_hyphen == live` 가 「둘 다 같은 방식으로 틀린」 경우를 못 가른다.
    실측: stem 조인은 `golangci-lint` 를 놓쳐 5 대신 4를 낸다.
    """
    from src.analyzer.io.static import PROVISIONED_ANALYZERS  # noqa: PLC0415

    stems = set(_fail_open_adapters())
    naive = stems & PROVISIONED_ANALYZERS
    by_name = {n for s in stems for n in _registered_names(s)} & PROVISIONED_ANALYZERS
    dropped = sorted(by_name - naive)
    # 🔴 무엇이 떨어지는지를 **이름으로** 단언한다. `naive < by_name` 만 두면 그 줄을
    #    `True or ...` 로 바꿔도 아무도 모른다(뮤테이션 실측: 초록이었다).
    #    자기검사가 스스로를 지키지 못하면 그것도 거짓 집행자다.
    # Assert *which* member the stem join drops, not merely that it drops something.
    assert dropped == ["golangci-lint"], (
        f"stem 조인이 떨어뜨리는 것: {dropped} (기대: ['golangci-lint'])\n"
        "   달라졌다면 (a) golangci-lint 부채가 닫혔거나 (b) 이름이 갈리는 어댑터가 새로 생겼다.\n"
        "   (a) 면 이 자기검사를 지우고, (b) 면 위 조인이 그것도 잡는지 확인하라."
    )
