"""분석기 어댑터의 fail-open 재고 — 새로 늘지 않게 못 박는다 (감사 A2 확장, #1519).

🔴 semgrep 하나를 고치는 것으로는 부족하다. 같은 형태가 **14개 어댑터**에 더 있다(실측):

    비-JSON stdout -> return []   8개
    JSONDecodeError -> return []  14개
    그 14개 중 `raise` 가 있는 것  0개

그리고 그것이 실제로 무엇을 만드는지도 쟀다 — **17개 언어**는 provisioned 분석기가
**전부** fail-open 어댑터다. 그 언어에서 분석기가 죽으면 `incomplete=False` 인 채
이슈 0건이 되고, 정적 점수는 만점이며 `auto_merge` 차단이 걸리지 않는다:

    java · go · ruby · php · rust · csharp · kotlin · swift · scala · elixir
    clojure · shell · html · sql · terraform · dockerfile · solidity

이 파일은 **고치지 않는다** — 그것은 별도 PR 의 일이다. 여기서 하는 것은 두 가지다:

1. 현재 fail-open 인 어댑터 집합을 **명시적으로 적어 둔다.** 목록에 없는 어댑터가
   fail-open 이면 red — 즉 **새로 늘지 않는다.**
2. 목록이 **비면 red** 다. 전부 고친 뒤에는 이 파일을 지우라는 신호다
   (공허한 allowlist 가 영구히 남는 것을 막는다).

The debt is inventoried, not hidden: the set may shrink but never grow.
"""
from __future__ import annotations

import ast
import io
from pathlib import Path

_TOOLS = Path("src/analyzer/io/tools")

# 🔴 현재 fail-open 인 어댑터 — **줄이기만 한다.** 새 이름을 여기 넣지 마라.
# 고친 어댑터는 이 목록에서 빼면 된다.
KNOWN_FAIL_OPEN: frozenset[str] = frozenset({
    "dart_analyze", "golangci_lint", "hadolint", "htmlhint", "ktlint",
    "phpstan", "psscriptanalyzer", "rubocop", "shellcheck", "slither",
    "sqlfluff", "stylelint", "swiftlint", "tflint",
})


def _returns_empty_list(nodes) -> bool:
    mod = ast.Module(body=list(nodes), type_ignores=[])
    return any(
        isinstance(n, ast.Return) and isinstance(n.value, ast.List) and not n.value.elts
        for n in ast.walk(mod)
    )


def _fail_open_adapters() -> set[str]:
    """비-JSON stdout 또는 JSON 파싱 실패를 `[]` 로 삼키는 어댑터 이름."""
    found: set[str] = set()
    for path in sorted(_TOOLS.glob("*.py")):
        if path.name.startswith("_") or path.name == "__init__.py":
            continue
        tree = ast.parse(io.open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.If) and "startswith" in ast.unparse(node.test):
                if _returns_empty_list(node.body):
                    found.add(path.stem)
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                if "JSONDecodeError" in ast.unparse(node.type) and _returns_empty_list(node.body):
                    found.add(path.stem)
    return found


# ─── 계기 자기검증 ───────────────────────────────────────────────────────────


def test_the_detector_actually_finds_something():
    """🔴 탐지기가 0건을 내면 이 파일 전체가 공허하다."""
    assert _fail_open_adapters(), (
        "fail-open 어댑터를 하나도 못 찾았다 — AST 탐지기가 깨졌거나 "
        "관용구가 바뀌었다. 목록이 진짜 비었다면 이 파일을 지워라."
    )


def test_a_hardened_adapter_is_not_flagged():
    """🔴 대조군 — 이미 고친 어댑터(`semgrep`·`python`)는 잡히지 않아야 한다.

    잡힌다면 탐지기가 `raise` 와 `return []` 을 구분하지 못하는 것이다.
    """
    flagged = _fail_open_adapters()
    for hardened in ("semgrep", "python"):
        assert hardened not in flagged, (
            f"{hardened} 이 fail-open 으로 잡혔다 — 수정이 되돌아갔거나 탐지기가 틀렸다"
        )


# ─── 재고 ────────────────────────────────────────────────────────────────────


def test_fail_open_set_does_not_grow():
    """🔴 fail-open 어댑터가 **늘지 않는다** — 새 어댑터는 fail-closed 로 써라.

    늘면 그만큼 언어가 조용히 미분석 상태로 만점을 받게 된다.
    """
    new = sorted(_fail_open_adapters() - KNOWN_FAIL_OPEN)
    assert not new, (
        f"fail-open 어댑터가 늘었다: {new}. 비-JSON stdout 과 JSON 파싱 실패는 "
        "`raise` 로 올려라 — `[]` 는 «이슈 0건 · 완전» 이 되어 미분석 코드가 auto-merge 된다. "
        "형제 관용구: src/analyzer/io/tools/semgrep.py::_fail"
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
