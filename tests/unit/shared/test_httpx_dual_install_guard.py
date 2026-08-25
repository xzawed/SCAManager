"""httpx / httpx2 두 벌 공존에서 오는 함정을 정적으로 막는다 (#1501).

이 환경에는 HTTP 라이브러리가 **두 벌** 있다:

- `httpx` — 이 리포가 직접 쓴다 (`src/` **23개 파일**이 import, AST 실측)
- `httpx2` — `anthropic` / `openai` SDK 가 **내부적으로** 쓴다 (전이 의존, 직접 핀 아님)

공유하는 예외 이름 **28종이 전부 서로 다른 클래스다** (실측: `is` 비교 28/28 False).
따라서 `except httpx.HTTPError` 는 httpx2 예외를 **구조적으로 못 잡는다.**

지금은 무해하다 — SDK 가 전송 오류를 `anthropic.APIConnectionError` 등 자기 타입으로
감싸고, SDK 호출부 4곳(`review_code` · `_call_insight_claude_api` ·
`repo_insight_narrative` · `call_openai_verifier`)이 전부 `except Exception` 이다.
**그 broad except 를 좁히려는 사람이 이 파일을 먼저 읽어야 한다.**

🔴 실측으로 정정한 것 (초안이 틀렸던 지점 — 같은 오류를 반복하지 않도록 남긴다):

- `alias_httpx()` 는 **조용히 무력화하지 않는다.** `import httpx` 가 이미 일어난 뒤라면
  `RuntimeError: httpx was already imported` 를 던진다. 조용한 치환은 **어떤 httpx import
  보다도 먼저** 불렸을 때뿐이다 — 그래서 아래 G1 은 「조용한 사고」가 아니라
  「기동 순서에 따라 갈리는 사고」를 막는다.
- `openai` 는 `http_client=` 를 **검사 없이 통과시키지 않는다.** `httpx2.Client` 와
  레거시 `httpx.Client` 를 **둘 다 허용**하는 allowlist 가 있다. 반면 `anthropic` 은
  `TypeError: Expected an instance of httpx2.Client` 로 거부한다. 즉 위험은 「무검사」가
  아니라 **두 SDK 의 수용 범위가 다르다**는 비대칭이다.

🔴 **문자열 탐색이 아니라 AST 로 판정한다.** 첫 판은 `"alias_httpx" in text` 로 짰다가
**그 규칙을 설명하는 docstring 자체를 막았다** — 산문을 막는 가드는 정정 기록과 주의문을
불가능하게 만든다. 여기서는 실제 **호출/키워드 인자 노드**만 센다.

🔴 이 가드들이 **못 잡는 것** (Grok 리뷰 실측, 현재 트리에는 0건):
별칭 import(`AsyncAnthropic as AC`), `**kwargs` 스플랫, 팩토리 함수 경유,
계산된 `getattr`, `importlib.import_module("httpx2")`, `exec`.
정적 판정의 한계이지 구현 버그가 아니다 — 「전부 막는다」고 읽지 마라.

Two HTTP libraries coexist; 28 shared exception names are all distinct types. Guards are
AST-based (a substring version blocked its own documentation) and do not catch aliased
imports, kwargs splatting, or dynamic imports.
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


def test_docstring_facts_are_still_true():
    """🔴 이 파일 docstring 이 주장하는 수치를 **실측으로 고정**한다.

    초안의 산문이 네 군데 틀렸다(예외 28종을 11종으로, 23파일을 24파일로 등).
    산문만 두면 또 틀린다 — 주장하는 숫자는 테스트가 재게 한다.
    """
    import inspect as _inspect  # noqa: PLC0415

    import httpx  # noqa: PLC0415
    import httpx2  # noqa: PLC0415

    hx = {n for n, o in vars(httpx).items() if _inspect.isclass(o) and issubclass(o, Exception)}
    h2 = {n for n, o in vars(httpx2).items() if _inspect.isclass(o) and issubclass(o, Exception)}
    shared = hx & h2
    assert len(shared) == 28, f"공유 예외 이름이 28종이 아니다: {len(shared)} — docstring 갱신 필요"

    same = [n for n in shared if getattr(httpx, n) is getattr(httpx2, n)]
    assert not same, f"두 벌이 같은 클래스를 공유한다 — 전제가 무너졌다: {same}"

    importers = {
        f.name
        for f, tree in _src_trees()
        for n in ast.walk(tree)
        if (isinstance(n, ast.Import) and any(a.name.split(".")[0] == "httpx" for a in n.names))
        or (isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "httpx")
    }
    assert len(importers) == 23, (
        f"src/ 에서 httpx 를 import 하는 파일이 23개가 아니다: {len(importers)} — docstring 갱신 필요"
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
