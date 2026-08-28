"""분석기 어댑터의 fail-open 재고 — 새로 늘지 않게 못 박는다 (감사 A2 확장, #1519 / #1521).

`static.py::_run_analyzers` 의 계약: `run()` 이 **예외를 올릴 때만** `incomplete` 로 승격한다.
`[]` 를 돌려주면 그 실패가 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다.

## 🔴 이 파일의 이전 판은 거짓 집행자였다 (실측)

이전 탐지기는 **관용구 두 개**만 알았다 — `startswith` 판정의 `return []` 과
`JSONDecodeError` 핸들러의 `return []`. 관용구 열거는 열거하지 않은 형태에 원리적으로 눈먼다:

    리포에 실재하는 fail-open 형태 7종 중  탐지 2종 · 눈먼 것 5종
    뮤테이션: 눈먼 형태로 새 어댑터 2개 투입 → 가드 exit 0 (5 passed)

그래서 `KNOWN_FAIL_OPEN` 에 적혀 있던 14개는 **실제 집합이 아니라 눈먼 탐지기의 출력**이었다.
재집계 20 → W1 5개(관측면 0)와 W3 3개(스폰 축)를 fail-closed 로 돌려 현재 **12개**다 — 남은 것은
전부 W2(전담 축 소실)다. 형태 7종은 `tests/unit/analyzer/fixtures/` 에 픽스처로 박혀 있고,
각 파일 docstring 이 그 형태를 쓰는 실물 어댑터 좌표를 든다.

## 판정을 관용구에서 파생값으로 바꿨다

`[]` 가 정당한 자리는 **두 축뿐**이고, 둘 다 다른 기전이 이미 담당한다:

    except subprocess.TimeoutExpired → `ctx.timed_out` 이 incomplete 로 승격한다
    except FileNotFoundError         → 조달 축(`unavailable_tools`)이 담당한다

그 밖의 `[]` 는 전부 「분석 못 했는데 깨끗하다고 보고」다. 그래서 판정은 열거가 아니라 파생이다:

    A. 모듈 안 어느 함수에도 `raise` 가 없다      → 크래시 판별식이 아예 없다
    B. 위 두 축 밖의 `return []` 이 하나라도 있다  → 그 자리가 미분석을 삼킨다

두 축 모두 **모듈의 모든 함수**를 본다. 「`run` 과 `_parse*` 만」처럼 이름으로 범위를
정하면 다르게 명명된 헬퍼에 눈멀고, 그것은 관용구 열거와 같은 실패다.

`except OSError` 는 B 로 걸린다 — `shutil.which` 를 통과한 뒤의 ENOEXEC(깨진 shebang)·
PermissionError·TOCTOU 는 「바이너리 부재」가 아니라 미분석이다. 이 구별은 `FileNotFoundError`
로 좁힌 어댑터만 갖는다(실측 10/23). 어느 것이 남았는지는 이 파일이 아니라 **탐지기**가
말한다 — 아래 목록은 그 출력과 대조될 뿐이고, 목록을 손으로 읽어 판단하지 않는다.

## 이 파일이 하는 것

1. 현재 fail-open 인 어댑터 집합을 명시한다. 목록 밖 어댑터가 fail-open 이면 **red**.
2. 목록이 **비면 red** — 부채가 사라졌으니 이 파일을 지우라는 신호다.
3. 탐지기가 다시 눈멀면 **red** — 픽스처 7종을 전부 봐야 한다.

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
    # 남은 12개는 #1557 W2 다: semgrep 이 같은 언어를 덮지만 **전담 축은 사라진다**.
    "clippy", "cppcheck", "dotnet_format", "golangci_lint", "hadolint",
    "htmlhint", "ktlint", "phpstan", "rubocop", "shellcheck", "slither",
    "swiftlint",
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
    return reasons


def _fail_open_adapters(root: Path = _TOOLS) -> set[str]:
    """분석 실패를 `[]` 로 삼키는 어댑터 이름 — 판정은 모듈 docstring 의 A·B 축."""
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
