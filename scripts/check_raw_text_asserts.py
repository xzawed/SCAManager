#!/usr/bin/env python3
"""PR 이 새로 쓴 «원문 글자 포함» 단언을 막는다 — 바뀐 줄 래칫 (회고 원장 L12 P2-52 · 사용자 11-16 결정).

B8 floor(`check_guard_fail_open.py`)는 파일 단위다 — 파일 어디서든 구조 도구를 한 번 부르면 그 파일의 맨
`assert "글자" in text` 가 전부 지나간다. 그런 단언은 주석 · docstring · 산문이 통과시킨다(#1136 클래스).
이 가드는 PR 이 더하거나 고친 줄의 단언만 본다 — 이미 있던 것은 그 줄을 고칠 때 함께 고친다.

## 막는 것

`assert` 안의 `"글자" in X` · `"글자" not in X`(왼쪽이 문자열 리터럴 · f-문자열)에서 X 가 **리포 소스 원문**일 때.

- 원문 = 리포 경로를 읽은 `read_text(...)` · `read_bytes(...)` · `open(...).read()` · `with open(...) as f` 의 `f.read()`,
  그리고 `inspect.getsource(...)`. 리포 경로 = `__file__` 에서 온 경로(`.parent` · `parents[n]` · `resolve()` · `/` 결합) ·
  그것을 담은 이름 · 상대 경로 리터럴(`open("src/x.css")` · `Path("docs/x.md")`).
- 원문을 그대로 두는 변형 = `decode` · `lower` · `upper` · `casefold` · `strip` 류 · `replace` · 자르기(`text[a:b]`) ·
  `split` · `partition` 결과의 한 조각 · `+` 로 이어 붙임.
- 따라가는 길 = 같은 함수 · 모듈 최상위의 이름 대입, 원문을 돌려주는 모듈 함수의 호출, 원문을 돌려주는 픽스처를 받은 인자.

그 밖의 호출(`strip_css_comments` · `template_code` · `json.loads` · `ast.parse` …)을 거친 값은 구조를 읽은 것이라 보지 않는다.

## 면제

정당하게 원문 글자 자체를 재는 단언은 그 줄에 `# fail-open-reviewed: <사유>` 주석(B8 과 같은 표지 · 주석 토큰만).

## 🔴 한계 (못 보는 것)

- 위 목록 밖의 원문 보존 변형을 거치면 못 본다 — 공백 접기 `" ".join(text.split())`(join) · `textwrap.dedent(text)`(dedent) ·
  `text.removeprefix(...)`(removeprefix) 등.
- 경로가 인자 · 픽스처로 오면(parametrize 된 리포 파일 포함) 따라가지 않는다. 시험이 만든 임시 파일(`tmp_path`)은
  원문이 아니라 출력이다 — 주석이 끼어들 자리가 없어 이 가드의 질문이 아니다.
- 클래스 속성 · 다른 모듈에서 가져온 원문 · 픽스처를 받는 픽스처(두 단계) · `self` 메서드는 따라가지 않는다.
- 흐름을 보지 않는다 — 한 함수에서 한 번이라도 원문을 대입한 이름은 그 함수 내내 원문으로 본다.

Diff-scoped ratchet: blocks assertions this PR wrote that search raw file text for a literal.
"""
from __future__ import annotations

import ast
import io
import re
import subprocess  # nosec B404 — git 만, 인자는 이 파일의 상수 + 커밋 이름
import sys
import tokenize
import warnings

_ESCAPE = "# fail-open-reviewed:"
# 원문을 읽는 메서드 / methods that read raw file text
_READS = frozenset({"read_text", "read_bytes"})
# 원문을 그대로 두는 메서드 — 결과도 원문이다 / methods whose result is still raw text
_KEEPS_TEXT = frozenset({"decode", "lower", "upper", "casefold", "strip", "lstrip", "rstrip", "replace"})
# 원문을 조각내는 메서드 — 그 결과의 한 조각이 원문이다 / methods whose result's pieces are raw text
_PIECES = frozenset({"split", "rsplit", "partition", "rpartition"})
# 경로를 그대로 두는 메서드 — 리포 경로에 부르면 리포 경로다 / path methods that keep a repo path a repo path
_KEEPS_PATH = frozenset({"resolve", "absolute", "joinpath", "with_name", "with_suffix"})
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _make_stdout_safe() -> None:
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss)."""
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 재구성 불가한 스트림(파이프·구버전) — 출력 인코딩은 최선 노력 / best-effort only


def _own_nodes(scope: ast.AST):
    """그 범위 자신의 노드 — 안에 든 함수 · 람다 · 클래스의 몸통으로는 내려가지 않는다."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef):
            continue
        stack.extend(ast.iter_child_nodes(node))


class _Taint:
    """한 범위에서 원문인 이름 · 리포 경로인 이름 · 파일 핸들, 그리고 모듈의 원문 함수."""

    def __init__(self, names: set[str], paths: set[str], handles: set[str], funcs: set[str]):
        self.names, self.paths, self.handles, self.funcs = names, paths, handles, funcs

    def repo_path(self, node: ast.AST) -> bool:
        """리포 경로인가 — `__file__` 에서 온 경로 · 그것을 담은 이름 · 상대 경로 리터럴. 인자 · 임시 경로는 아니다."""
        if isinstance(node, ast.Name):
            return node.id == "__file__" or node.id in self.paths
        if isinstance(node, ast.Constant):
            return isinstance(node.value, str)
        if isinstance(node, ast.Attribute):
            return node.attr == "parent" and self.repo_path(node.value)
        if isinstance(node, ast.Subscript):
            return (isinstance(node.value, ast.Attribute) and node.value.attr == "parents"
                    and self.repo_path(node.value.value))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            return self.repo_path(node.left)
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr in _KEEPS_PATH:
                return self.repo_path(func.value)
            named = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            return named == "Path" and bool(node.args) and self.repo_path(node.args[0])
        return False

    def is_read(self, node: ast.AST) -> bool:
        """리포 소스를 읽는 호출인가 — 리포 경로의 `read_text()` · `read_bytes()` · `open(..).read()` · 핸들의
        `.read()` · `inspect.getsource(..)`."""
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id == "getsource"
        if not isinstance(func, ast.Attribute):
            return False
        if func.attr == "getsource":
            return True
        if func.attr in _READS:
            return self.repo_path(func.value)
        if func.attr != "read":
            return False
        owner = func.value
        if isinstance(owner, ast.Call) and isinstance(owner.func, ast.Name) and owner.func.id == "open":
            return bool(owner.args) and self.repo_path(owner.args[0])
        return isinstance(owner, ast.Name) and owner.id in self.handles

    def raw(self, node: ast.AST) -> bool:
        """이 식이 파일 원문(또는 원문을 그대로 둔 변형)인가."""
        if self.is_read(node):
            return True
        if isinstance(node, ast.Name):
            return node.id in self.names
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id in self.funcs
            return isinstance(node.func, ast.Attribute) and node.func.attr in _KEEPS_TEXT and self.raw(node.func.value)
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                return self.raw(node.value)
            return self.pieces(node.value)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.raw(node.left) or self.raw(node.right)
        return False

    def pieces(self, node: ast.AST) -> bool:
        """조각마다 원문인 값인가 — 원문의 `split(...)` · `partition(...)`."""
        return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _PIECES and self.raw(node.func.value))


def _assigned_names(scope: ast.AST) -> set[str]:
    """그 범위에서 대입되는 이름 — 지역 이름이 같은 이름의 원문 전역을 가린다."""
    names: set[str] = set()
    for node in _own_nodes(scope):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            names.add(node.id)
    return names


def _scope_taint(scope: ast.AST, inherited: _Taint | None, funcs: set[str], params: set[str]) -> _Taint:
    """그 범위의 원문 · 리포 경로 이름 — 대입 순서와 무관하게 세 번 돈다(흐름 무감각)."""
    local = _assigned_names(scope)
    names = (inherited.names - local) if inherited else set()
    paths = (inherited.paths - local) if inherited else set()
    taint = _Taint(names | params, paths, set(), funcs)
    for _ in range(3):
        for node in _own_nodes(scope):
            if isinstance(node, ast.With | ast.AsyncWith):
                for item in node.items:
                    call = item.context_expr
                    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "open"
                            and call.args and taint.repo_path(call.args[0])
                            and isinstance(item.optional_vars, ast.Name)):
                        taint.handles.add(item.optional_vars.id)
            elif isinstance(node, ast.Assign | ast.AnnAssign) and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name) and taint.raw(node.value):
                        taint.names.add(target.id)
                    elif isinstance(target, ast.Name) and not isinstance(node.value, ast.Constant) \
                            and taint.repo_path(node.value):
                        taint.paths.add(target.id)
                    elif isinstance(target, ast.Tuple) and taint.pieces(node.value):
                        taint.names.update(e.id for e in target.elts if isinstance(e, ast.Name))
    return taint


def _is_fixture(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for deco in fn.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if isinstance(target, ast.Name) and target.id == "fixture":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "fixture":
            return True
    return False


def _returns_raw(fn: ast.AST, taint: _Taint) -> bool:
    return any(isinstance(node, ast.Return | ast.Yield) and node.value is not None and taint.raw(node.value)
               for node in _own_nodes(fn))


def _reviewed_lines(src: str) -> set[int]:
    """면제 표지가 **주석 토큰**으로 있는 줄 — 문자열 안의 표지는 인정하지 않는다."""
    lines: set[int] = set()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT and _ESCAPE in tok.string:
            lines.add(tok.start[0])
    return lines


def _is_literal(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)) or isinstance(node, ast.JoinedStr)


def _offending_compare(test: ast.AST, taint: _Taint) -> ast.Compare | None:
    """단언 식 안의 `"글자" in 원문` — 첫 것 하나."""
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        operands = [node.left, *node.comparators]
        for i, op in enumerate(node.ops):
            if isinstance(op, ast.In | ast.NotIn) and _is_literal(operands[i]) and taint.raw(operands[i + 1]):
                return node
    return None


def violations_in(src: str, added: set[int]) -> list[tuple[int, str]]:
    """그 소스에서 `added` 줄에 걸친 «원문 글자 포함» 단언 — (줄, 비교식). 구문 오류는 SyntaxError 로 올린다."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(src)
    reviewed = _reviewed_lines(src)
    module = _scope_taint(tree, None, set(), set())
    top = [n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]
    funcs: set[str] = set()
    fixtures: set[str] = set()
    for _ in range(len(top) + 1):            # 원문 함수가 원문 함수를 부를 수 있다 — 고정점까지
        before = (len(funcs), len(fixtures))
        for fn in top:
            if _returns_raw(fn, _scope_taint(fn, module, funcs, set())):
                (fixtures if _is_fixture(fn) else funcs).add(fn.name)
        if (len(funcs), len(fixtures)) == before:
            break
    module.funcs = funcs

    scopes: list[tuple[ast.AST, _Taint]] = [(tree, module)]
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            params = {a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
            scopes.append((node, _scope_taint(node, module, funcs, params & fixtures)))
    found: list[tuple[int, str]] = []
    for scope, taint in scopes:
        for node in _own_nodes(scope):
            if not isinstance(node, ast.Assert):
                continue
            span = set(range(node.lineno, (node.end_lineno or node.lineno) + 1))
            if not span & added or span & reviewed:
                continue
            hit = _offending_compare(node.test, taint)
            if hit is not None:
                found.append((node.lineno, (ast.get_source_segment(src, hit) or "")[:90]))
    return sorted(found)


def _git(*args: str) -> str:
    """git → stdout. 실패 시 **loud 종료**(fail-CLOSED) — 빈 출력을 «위반 없음» 으로 읽지 않게.

    🔴 **PARITY GUARD** — 형제 diff 가드(`check_dual_import.py` 등)와 같은 계약이다
    (`tests/unit/scripts/test_guard_git_failclosed.py`).
    Fail-closed git helper shared in contract with the sibling diff-scoped guards.
    """
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=False,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print(f"🔴 git 실패 — 가드 실행 불가 (fail-closed): git {' '.join(args)}")
        print(f"   {(result.stderr or '').strip()[:300]}")
        sys.exit(2)
    return result.stdout or ""


def _added_lines(base: str, head: str, path: str) -> set[int]:
    """그 파일에서 이 PR(병합 기점 → head)이 더하거나 고친 줄."""
    added: set[int] = set()
    for line in _git("diff", "-U0", f"{base}...{head}", "--", path).splitlines():
        m = _HUNK.match(line)
        if m:
            start, count = int(m.group(1)), int(m.group(2) or 1)
            added.update(range(start, start + count))
    return added


def main(argv: list[str]) -> int:
    _make_stdout_safe()
    base = argv[1] if len(argv) > 1 else "origin/main"
    head = argv[2] if len(argv) > 2 else "HEAD"
    names = _git("diff", "--name-only", "--diff-filter=ACMR", f"{base}...{head}", "--", "tests", "e2e")
    paths = [p for p in names.splitlines() if p.endswith(".py")]
    if not paths:
        print("✅ 바뀐 시험 파일 없음 — 잴 것이 없다")
        return 0
    found: list[tuple[str, int, str]] = []
    broken: list[str] = []
    for path in paths:
        added = _added_lines(base, head, path)
        if not added:
            continue
        try:
            found += [(path, line, text) for line, text in violations_in(_git("show", f"{head}:{path}"), added)]
        except SyntaxError:
            broken.append(path)
    if broken:
        print("🔴 구문이 깨져 잴 수 없는 시험 파일 — «위반 없음» 이 아니다:")
        for path in broken:
            print(f"   - {path}")
        return 1
    if found:
        print(f"🔴 이 PR 이 쓴 «원문 글자 포함» 단언 {len(found)}건 — 주석 · docstring · 산문이 통과시킨다(#1136 클래스):")
        for path, line, text in found:
            print(f"   - {path}:{line}  {text}")
        print("해결: 구조를 읽고 판정한다 — 템플릿 · JS 는 tests/unit/ui/_code_view.py, CSS 는 주석을 지운 본문,")
        print("   그 밖은 ast · 파서. 정당하게 원문 글자 자체를 재면 그 줄에 `# fail-open-reviewed: <사유>`.")
        return 1
    print(f"✅ 이 PR 이 쓴 «원문 글자 포함» 단언 없음 — 바뀐 시험 파일 {len(paths)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
