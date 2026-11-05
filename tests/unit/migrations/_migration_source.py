"""마이그레이션 소스에서 «실제로 보내는 SQL» 과 모듈 상수를 구문 트리로 읽는다.

원문 substring 검사는 주석·docstring 이 그 SQL 을 인용해도 통과한다. 여기서는 `execute(...)` ·
`text(...)` 의 첫 인자로 넘기는 글자만 SQL 로 센다 — 주석과 docstring 은 그 자리에 올 수 없다.
Reads the SQL a migration actually sends, and its module constants, from the syntax tree.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

_SQL_CALLS = frozenset({"execute", "text"})
_SQL_LINE_COMMENT = re.compile(r"--[^\n]*")


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def sql_literals(path: Path, function: str | None = None) -> list[str]:
    """`execute(...)` · `text(...)` 의 첫 인자 글자 — SQL `--` 주석을 지우고 공백을 한 칸으로 접는다.

    `function` 을 주면 그 이름의 최상위 함수 안만 본다 — `upgrade` 의 단언이 `downgrade` 의 SQL 로
    통과하지 않게. 그런 함수가 정확히 하나가 아니면 바로 실패한다(못 재면 red).
    """
    tree = _tree(path)
    scope: ast.AST = tree
    if function is not None:
        found = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function]
        if len(found) != 1:
            raise AssertionError(f"{path.name}: 최상위 함수 `{function}` 가 {len(found)}개다")
        scope = found[0]
    out = []
    for n in ast.walk(scope):
        if not (isinstance(n, ast.Call) and n.args):
            continue
        name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
        first = n.args[0]
        if name in _SQL_CALLS and isinstance(first, ast.Constant) and isinstance(first.value, str):
            out.append(" ".join(_SQL_LINE_COMMENT.sub("", first.value).split()))
    return out


def module_constants(path: Path) -> dict[str, object]:
    """최상위 `NAME = <리터럴>` 대입 — `ast.literal_eval` 로 풀리는 값만."""
    out: dict[str, object] = {}
    for n in _tree(path).body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            try:
                out[n.targets[0].id] = ast.literal_eval(n.value)
            except (ValueError, TypeError, SyntaxError):
                continue
    return out
