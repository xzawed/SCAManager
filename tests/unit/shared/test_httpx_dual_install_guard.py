"""httpx / httpx2 두 벌 공존에서 오는 함정을 정적으로 막는다 (#1501).

🔴 이 환경에는 HTTP 라이브러리가 두 벌 있다 — 리포가 직접 쓰는 `httpx` 와,
anthropic/openai SDK 가 내부적으로 쓰는 `httpx2`. 두 벌의 예외 클래스는 이름만 같고
서로 다른 타입이라 `except httpx.HTTPError` 가 httpx2 예외를 구조적으로 못 잡는다.
사실 관계는 `src/shared/http_client.py` 모듈 docstring 에 있다.

🔴 **문자열 탐색이 아니라 AST 로 판정한다.** 첫 판은 `"alias_httpx" in text` 로 짰다가
**그 규칙을 설명하는 docstring 자체를 막았다** — 산문을 막는 가드는 정정 기록과 주의문을
불가능하게 만든다. 여기서는 실제 **호출/키워드 인자 노드**만 센다.

Guards are AST-based, not substring-based: the first version blocked the very docstring that
documents the rule. Prose must stay quotable.
"""
from __future__ import annotations

import ast
import pathlib

_SRC = pathlib.Path(__file__).resolve().parents[3] / "src"


def _src_trees() -> list[tuple[pathlib.Path, ast.AST]]:
    out = []
    for f in sorted(_SRC.rglob("*.py")):
        try:
            out.append((f, ast.parse(f.read_text(encoding="utf-8"))))
        except SyntaxError:  # pragma: no cover - 구문 오류 파일은 별도 가드의 몫
            continue
    return out


def _rel(f: pathlib.Path) -> str:
    return f.relative_to(_SRC.parent).as_posix()


def test_source_tree_is_scannable():
    """계기 자기검증 — 파일을 못 찾으면 아래 단언이 공허하다."""
    trees = _src_trees()
    assert len(trees) > 100, f"src/ 에서 {len(trees)}개 파일만 파싱했다 — 스캐너 점검 필요"


def test_ast_guard_detects_a_planted_call():
    """계기 자기검증(반대 방향) — 실제 호출을 심으면 잡아야 하고, 산문은 안 잡아야 한다."""
    planted = ast.parse("import httpx2\nhttpx2.alias_httpx()\n")
    calls = [
        n for n in ast.walk(planted)
        if isinstance(n, ast.Call) and "alias_httpx" in ast.unparse(n.func)
    ]
    assert calls, "심은 호출을 못 잡았다 — 판정기 고장"

    prose = ast.parse('"""절대 alias_httpx() 를 부르지 마라."""\nx = 1\n')
    prose_calls = [
        n for n in ast.walk(prose)
        if isinstance(n, ast.Call) and "alias_httpx" in ast.unparse(n.func)
    ]
    assert not prose_calls, "docstring 언급을 호출로 오판했다 — 산문을 막는 가드가 된다"


def test_alias_httpx_is_never_called():
    """🔴 `httpx2.alias_httpx()` 는 `import httpx` 를 전역에서 httpx2 로 바꾼다.

    한 번이라도 불리면 리포의 `except httpx.*` 절이 **조용히 무력화**된다 —
    잡히던 오류가 안 잡히고, 그 실패는 로그에도 안 남는다.
    """
    hits = [
        f"{_rel(f)}:{n.lineno}"
        for f, tree in _src_trees()
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and "alias_httpx" in ast.unparse(n.func)
    ]
    assert not hits, (
        "alias_httpx() 호출 — import httpx 가 전역에서 httpx2 로 해석돼 "
        f"except httpx.* 절이 무력화된다: {hits}"
    )


def test_http_client_kwarg_is_never_passed_to_sdk_clients():
    """🔴 SDK 클라이언트에 `http_client=` 를 넘기면 안 된다 — 두 라이브러리가 비대칭이다.

    anthropic 은 httpx 클라이언트를 `TypeError` 로 즉시 거부하지만, **openai 는 검사 없이
    통과**해 실제 요청까지 나간다. 후자는 조용히 잘못된 전송 계층을 쓰게 된다.

    리포 자신의 `httpx.AsyncClient(...)` 구성은 대상이 아니다 — SDK 생성자만 본다.
    """
    sdk_ctors = {"AsyncAnthropic", "Anthropic", "AsyncOpenAI", "OpenAI"}
    hits = []
    for f, tree in _src_trees():
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            name = ast.unparse(n.func).rsplit(".", 1)[-1]
            if name not in sdk_ctors:
                continue
            if any(kw.arg == "http_client" for kw in n.keywords):
                hits.append(f"{_rel(f)}:{n.lineno}")
    assert not hits, (
        "SDK 클라이언트에 http_client= 를 넘기는 지점 — anthropic 은 TypeError, "
        f"openai 는 조용히 통과한다: {hits}"
    )


def test_repo_does_not_import_httpx2_directly():
    """리포는 `httpx2` 를 직접 import 하지 않는다 — 두 벌을 섞으면 타입 판정이 깨진다."""
    hits = []
    for f, tree in _src_trees():
        for n in ast.walk(tree):
            if isinstance(n, ast.Import) and any(a.name.split(".")[0] == "httpx2" for a in n.names):
                hits.append(f"{_rel(f)}:{n.lineno}")
            elif isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "httpx2":
                hits.append(f"{_rel(f)}:{n.lineno}")
    assert not hits, f"httpx2 를 직접 import 하는 곳: {hits}"
