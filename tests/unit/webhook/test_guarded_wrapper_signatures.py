"""가드 래퍼는 `**kwargs` 가 아니라 **명시 파라미터**를 쓴다.

## 왜 (2026-07-19 #1122 → 회고 P1)

`**kwargs` 로 감싸면 pylint 가 호출을 검증하지 못한다(`missing-kwoa` 침묵). 그래서
감싸는 대상의 시그니처가 바뀌어도 래퍼는 **조용히 어긋난 채** 통과한다.

실측: `#1122` 에서 n8n 가드 래퍼를 `**kwargs` 로 썼다가 명시 파라미터로 바꾸자
**그 자리에서 자기 테스트의 인자 누락이 드러났다**. `**kwargs` 였다면 그대로 머지됐다.

그런데 같은 PR 이 안티패턴을 명문화하면서 **형제 래퍼(`telegram.py`)는 그대로 뒀다** —
회고가 P1 로 지목했다. 한쪽만 고치고 규칙만 적어두는 형태가 이 저장소의 반복 실패 클래스다.

## 이 가드가 보는 것

`_*_guarded` 명명 규약을 쓰는 백그라운드 가드 래퍼 전수. AST 로 `**kwargs` 수집을 금지한다
(문자열 검색이면 "kwargs 쓰지 말 것" 이라 쓴 주석이 걸린다 — #1135 학습).
"""
import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_SRC = _ROOT / "src"


def _guarded_wrappers():
    """`_..._guarded` 이름의 async 함수 전수 — (파일, 함수명, 노드)."""
    found = []
    for path in sorted(_SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and \
                    node.name.startswith("_") and node.name.endswith("_guarded"):
                found.append((path.relative_to(_ROOT).as_posix(), node.name, node))
    return found


def test_guarded_wrappers_exist():
    """대조군 — 가드 래퍼가 실재해야 이 테스트가 의미를 갖는다."""
    wrappers = _guarded_wrappers()
    assert wrappers, "`_*_guarded` 래퍼가 하나도 없다 — 명명 규약이 바뀌었는지 확인할 것"


def test_guarded_wrappers_do_not_use_kwargs():
    """🔴 가드 래퍼는 `**kwargs` 금지 — 시그니처 drift 가 조용히 통과한다.

    명시 파라미터면 pylint 가 호출을 검증하고, 감싸는 대상이 바뀌면 **loud 하게** 깨진다.
    """
    offenders = [
        f"{path}::{name}"
        for path, name, node in _guarded_wrappers()
        if node.args.kwarg is not None
    ]
    assert not offenders, (
        f"`**kwargs` 를 쓰는 가드 래퍼: {offenders}\n"
        "→ 감싸는 함수의 시그니처를 명시 파라미터로 복사할 것. kwargs 는 pylint 의 "
        "`missing-kwoa` 검증을 무력화해 인자 누락·시그니처 drift 를 숨긴다 (#1122 실측)."
    )


def test_guard_detects_a_synthetic_kwargs_wrapper():
    """탐지력 자가 검증 — 합성 `**kwargs` 래퍼를 실제로 잡는가."""
    tree = ast.parse("async def _x_guarded(**kwargs):\n    pass\n")
    fn = tree.body[0]
    assert fn.args.kwarg is not None, "탐지 기준(`args.kwarg`)이 동작하지 않는다"


def test_guard_allows_explicit_params():
    """부정 통제 — 명시 파라미터 래퍼는 통과해야 한다(가드가 전부 막으면 무의미)."""
    tree = ast.parse("async def _x_guarded(*, a: int, b: str = '') -> None:\n    pass\n")
    fn = tree.body[0]
    assert fn.args.kwarg is None
