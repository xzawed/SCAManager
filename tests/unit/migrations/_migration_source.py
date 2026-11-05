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
# SQL 문자열 리터럴(`'…'` · `"…"`, 겹따옴표 이스케이프 포함)은 남기고 `--` 줄 주석만 지운다.
# Keep SQL string literals (with doubled-quote escapes); drop only `--` line comments.
_SQL_TOKEN = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*")


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _strip_sql_comments(sql: str) -> str:
    return _SQL_TOKEN.sub(lambda m: "" if m.group(0).startswith("--") else m.group(0), sql)


def sql_literals(path: Path, function: str | None = None) -> list[str]:
    """`execute(...)` · `text(...)` 의 첫 인자 글자(소스 순서) — SQL `--` 주석을 지우고 공백을 한 칸으로 접는다.

    `function` 을 주면 그 이름의 최상위 함수(`def` · `async def`) 안만 본다 — `upgrade` 의 단언이
    `downgrade` 의 SQL 로 통과하지 않게. 그 안에서 정의한 함수의 SQL 도 그 함수의 것으로 센다.
    그런 함수가 정확히 하나가 아니면 바로 실패한다(못 재면 red).
    """
    tree = _tree(path)
    scope: ast.AST = tree
    if function is not None:
        found = [n for n in tree.body
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == function]
        if len(found) != 1:
            raise AssertionError(f"{path.name}: 최상위 함수 `{function}` 가 {len(found)}개다")
        scope = found[0]
    sent = []
    for n in ast.walk(scope):
        if not (isinstance(n, ast.Call) and n.args):
            continue
        name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
        first = n.args[0]
        if name in _SQL_CALLS and isinstance(first, ast.Constant) and isinstance(first.value, str):
            sent.append(((first.lineno, first.col_offset), " ".join(_strip_sql_comments(first.value).split())))
    return [sql for _, sql in sorted(sent)]


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
