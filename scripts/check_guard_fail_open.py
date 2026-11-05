#!/usr/bin/env python3
"""가드·시험의 **fail-open 저술 floor 게이트** — write-time (backlog B8).

파일을 읽어 pass/fail 을 판정하는 파이썬 코드가 구조 도구를 하나도 **부르지** 않으면 fail-open
후보로 차단한다. bare `X in file_text` 는 주석·docstring·산문이 통과시킨다(#1136 클래스).

## 표면

`scripts/check_*.py` · `.claude/hooks/*.py` · `tests/**/*.py` · `e2e/**/*.py` — 가드 인구는 시험으로
옮겨 갔다(정적 소스 검사 · 배선 검사). 표면 하나라도 0개면 glob 붕괴로, 구문이 깨진 파일이 하나라도
있으면 분석 불가로 실패한다(빈 범위 위의 초록 금지).

## 구조 도구로 세는 것 — 언급이 아니라 **호출**

- `ast` · `re` · `subprocess` 의 어떤 호출이든.
- 파서의 **읽기 입구** — `json.load(s)` · `yaml.safe_load` 등 · `tomllib.load(s)` ·
  `jinja2.Environment`/`Template`. `json.dumps` 같은 쓰기는 구조를 보지 않는다.
- `HTMLParser` 상속 — 상속해 쓰는 파서다.
- 리포 안 모듈에서 가져온 이름의 호출 — 그 모듈 자신이 위 도구를 부를 때(한 단계만).

## 🔴 한계 (floor 이지 천장이 아니다)

- 파일 단위다 — 구조 도구를 한 번이라도 부르면 그 파일의 다른 판정이 bare substring 이어도
  통과한다. «결정 표현식» 분석은 이 게이트가 하지 않는다.
- 파이썬만 읽는다 — `.claude/workflows/*.mjs` · 셸의 판정은 범위 밖이다.

escape: 정당한 substring-only 판정은 `# fail-open-reviewed: <사유>` 주석(실제 주석 토큰만 인정).
Floor gate: Python that reads a file and decides pass/fail must call a structural tool.
"""
import ast
import functools
import importlib
import io
import sys
import tokenize
import warnings
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
_HOOKS = _ROOT / ".claude" / "hooks"
_TESTS = _ROOT / "tests"
_E2E = _ROOT / "e2e"

_ESCAPE = "# fail-open-reviewed:"
# 구조 분석 도구 — 이 모듈의 **어떤** 호출이든 bare-substring 이 아니다.
# Structural modules: any call on them counts.
_STRUCTURAL_MODULES = {"ast", "re", "subprocess"}
# 파서 — 구조를 «읽는» 입구만 센다. 쓰기(`json.dumps` · `yaml.safe_dump`)는 구조를 보지 않는다.
# Parsers count only through their read entries; serializers never look at structure.
_PARSE_ENTRIES = {
    "json": frozenset({"load", "loads"}),
    "yaml": frozenset({"safe_load", "safe_load_all", "load", "load_all", "full_load", "full_load_all"}),
    "tomllib": frozenset({"load", "loads"}),
    "jinja2": frozenset({"Environment", "Template"}),
}
# 상속해 쓰는 파서 — `class P(HTMLParser)` 가 그 파서를 쓰는 모양이다.
# Parsers used by subclassing.
_PARSER_BASES = {"html.parser": frozenset({"HTMLParser"})}


def _parse(src: str) -> ast.Module:
    """`ast.parse` — 문자열 안의 잘못된 이스케이프가 내는 `SyntaxWarning` 은 이 게이트의 질문이 아니다."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        return ast.parse(src)


def _reads_a_file(tree: ast.AST) -> bool:
    """파일을 읽는가 — `.read_text(...)`/`.read_bytes(...)` 또는 `open(...)` 호출.

    🔴 `read_bytes` 포함 — bytes 로 읽어 decode 후 bare substring 판정하는 가드가 이름 집합 밖이면 미탐이다.
    Includes read_bytes: a guard reading bytes then substring-deciding escaped the name set.
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
            if name in ("read_text", "read_bytes", "open", "read"):
                return True
    return False


def _tool_names(tree: ast.AST) -> tuple[dict, set, set, set]:
    """구조 도구를 가리키는 이름을 import 에서 해소 — alias·from-import 인정.

    반환 = (모듈 별칭 → 셀 속성 집합(None = 전부), 직접 부르는 이름, 상속할 이름, 상속할 점 이름).
    🔴 `import re as r` / `from re import search` 를 못 보면 정당한 가드를 fail-open 오탐한다.
    Resolve names pointing at a structural tool, honoring aliases and from-imports.
    """
    modules: dict = {}      # `import re as r` → {"r": None}; `import json` → {"json": {"load", "loads"}}
    direct: set = set()     # `from re import search as s` → {"s"}; `from json import loads` → {"loads"}
    bases: set = set()      # `from html.parser import HTMLParser` → {"HTMLParser"}
    dotted: set = set()     # `import html.parser` → {"html.parser.HTMLParser"}; `... as hp` → {"hp.HTMLParser"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                bound = a.asname or a.name
                if a.name in _STRUCTURAL_MODULES:
                    modules[bound] = None
                elif a.name in _PARSE_ENTRIES:
                    modules[bound] = _PARSE_ENTRIES[a.name]
                elif a.name in _PARSER_BASES:
                    dotted |= {f"{a.asname or a.name}.{base}" for base in _PARSER_BASES[a.name]}
        elif isinstance(n, ast.ImportFrom) and not n.level:
            for a in n.names:
                if a.name == "*":  # `from re import *` — 그 모듈이 내보내는 이름 전부
                    direct |= _star_names(n.module)
                    bases |= _PARSER_BASES.get(n.module, frozenset())
                    continue
                bound = a.asname or a.name
                if n.module in _STRUCTURAL_MODULES or a.name in _PARSE_ENTRIES.get(n.module, ()):
                    direct.add(bound)
                if a.name in _PARSER_BASES.get(n.module, ()):
                    bases.add(bound)
    return modules, direct, bases, dotted


@functools.lru_cache(maxsize=None)
def _star_names(module: str | None) -> frozenset:
    """`from <module> import *` 가 묶는 구조 도구 이름 — 구조 모듈은 공개 이름 전부, 파서는 읽기 입구만."""
    if module in _STRUCTURAL_MODULES:
        mod = importlib.import_module(module)
        return frozenset(getattr(mod, "__all__", None) or (x for x in dir(mod) if not x.startswith("_")))
    return _PARSE_ENTRIES.get(module, frozenset())


def _public_names(tree: ast.Module) -> set:
    """`from helper import *` 가 묶는 이름 — `__all__` 리터럴이 있으면 그것, 없으면 `_` 로 안 시작하는 최상위 이름."""
    for n in tree.body:
        if (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets)
                and isinstance(n.value, (ast.List, ast.Tuple))):
            return {e.value for e in n.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            out |= {t.id for t in n.targets if isinstance(t, ast.Name)}
        elif isinstance(n, ast.Import):  # `import re` 도 별표로 넘어간다 — 파이썬이 그렇게 묶는다
            out |= {a.asname or a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out |= {a.asname or a.name for a in n.names if a.name != "*"}
    return {name for name in out if not name.startswith("_")}


def _dotted(node: ast.AST) -> str | None:
    """`html.parser.HTMLParser` 같은 점 이름 — 이름·속성 사슬이 아니면 None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        head = _dotted(node.value)
        return f"{head}.{node.attr}" if head is not None else None
    return None


def _inherits(cls: ast.ClassDef, bases: set, dotted: set) -> bool:
    """`class P(HTMLParser)` · `class P(html.parser.HTMLParser)` · `class P(hp.HTMLParser)`."""
    for b in cls.bases:
        if isinstance(b, ast.Name) and b.id in bases:
            return True
        if _dotted(b) in dotted:
            return True
    return False


def _module_file(base: Path, parts: list[str]) -> Path | None:
    """`a.b` → `a/b.py` 또는 패키지 `a/b/__init__.py` — 없으면 None."""
    if not parts:
        return None
    for candidate in (base.joinpath(*parts).with_suffix(".py"), base.joinpath(*parts, "__init__.py")):
        if candidate.is_file():
            return candidate
    return None


def _local_helper_names(tree: ast.AST, importer: Path, cache: dict) -> tuple[set, set]:
    """이 파일이 가져오는 리포 안 모듈 중 **그 자신이 구조 도구를 부르는** 것 — (모듈 별칭, 가져온 이름).

    `from ._contrast import strip_css_comments` · `from tests.unit.scripts._wiring_shape import
    surface_invokes` · `from tests.unit import _clean` 를 해소한다. 헬퍼의 헬퍼는 따라가지 않는다
    (한 단계 — 위임만 하는 헬퍼는 구조 도구 0 으로 남는다, fail-closed 쪽).
    Names imported from repo modules that themselves call a structural tool (one level deep).
    """
    aliases, names = set(), set()

    def helper_tree(path: Path) -> ast.Module | None:
        """구조 도구를 부르는 헬퍼면 그 구문 트리, 아니면(또는 못 읽으면) None."""
        key = str(path)
        if key not in cache:
            try:
                parsed = _parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError, OSError):
                parsed = None
            cache[key] = parsed if parsed is not None and _calls_structural_tool(parsed) else None
        return cache[key]

    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            base = _ROOT
            if n.level:
                base = importer.parent
                for _ in range(n.level - 1):
                    base = base.parent
            parts = n.module.split(".") if n.module else []
            for a in n.names:
                if a.name == "*":
                    target = _module_file(base, parts)
                    helper = helper_tree(target) if target is not None else None
                    if helper is not None:
                        names |= _public_names(helper)
                    continue
                # 하위 모듈이 먼저다 — `from tests.unit import _clean` 의 `tests/unit/__init__.py` 는 비어 있다.
                # Submodule first: the package __init__ next to it is usually empty.
                sub = _module_file(base, [*parts, a.name])
                if sub is not None:
                    if helper_tree(sub) is not None:
                        aliases.add(a.asname or a.name)
                    continue
                target = _module_file(base, parts)
                if target is not None and helper_tree(target) is not None:
                    names.add(a.asname or a.name)
        elif isinstance(n, ast.Import):
            for a in n.names:
                target = _module_file(_ROOT, a.name.split("."))
                if a.asname and target is not None and helper_tree(target) is not None:
                    aliases.add(a.asname)
    return aliases, names


def _calls_structural_tool(tree: ast.AST, importer: Path | None = None, cache: dict | None = None) -> bool:
    """실제로 **호출**되는 구조 도구가 있는가 — `re.search(...)` · `json.loads(...)` · `search(...)` ·
    `class P(HTMLParser)` · (importer 가 주어지면) 구조 헬퍼의 이름 호출.

    🔴 import·주석 언급이 아니라 호출을 본다(산문 통과 방지). alias·from-import 를 해소해 정당한
    가드 오탐도 막는다.
    """
    modules, direct, bases, dotted = _tool_names(tree)
    helper_aliases, helper_names = (
        _local_helper_names(tree, importer, cache if cache is not None else {})
        if importer is not None else (set(), set()))
    for n in ast.walk(tree):
        if isinstance(n, ast.ClassDef) and _inherits(n, bases, dotted):
            return True
        if not isinstance(n, ast.Call):
            continue
        func = n.func
        # <alias>.attr(...) — 예: re.search / r.search / json.loads / _contrast.strip_css_comments
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            owner = func.value.id
            if owner in modules and (modules[owner] is None or func.attr in modules[owner]):
                return True
            # 헬퍼 모듈의 함수 · 헬퍼에서 가져온 객체의 메서드(`_PATTERN.sub(...)`)
            if owner in helper_aliases or owner in helper_names:
                return True
        # 직접 부르는 이름 — 예: search(...) · loads(...) · strip_css_comments(...)
        if isinstance(func, ast.Name) and (func.id in direct or func.id in helper_names):
            return True
    return False


def _has_escape_comment(src: str) -> bool:
    """`# fail-open-reviewed:` 가 **실제 주석 토큰**인가 — docstring/문자열 내 언급은 불인정.

    🔴 bare `_ESCAPE in src` 는 그 자체가 fail-open 이다: 문자열/docstring 안 언급이 파일 전체를
    면제시켜, 이 게이트가 잡으려는 바로 그 클래스(면제 기제 자체의 산문 통과)를 재생산한다.
    tokenize 로 COMMENT 토큰만 본다. 토큰화 실패 시 면제 불인정(fail-closed).
    Recognize the escape only as a real comment token, never a substring in a string/docstring.
    """
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT and _ESCAPE in tok.string:
                return True
    except (tokenize.TokenError, IndentationError, SyntaxError):  # pragma: no cover
        return False
    return False


def _scan_targets() -> dict[str, list[Path]]:
    """스캔 표면 4종 — 표시 이름 → 파일. main() 이 표면별 붕괴(glob 0건)를 구별해 fail-closed 한다.

    Four scan surfaces keyed by label, so main() can fail closed per surface on collapse.
    """
    return {
        "scripts/check_*.py": sorted(_SCRIPTS.glob("check_*.py")),
        ".claude/hooks/*.py": sorted(_HOOKS.glob("*.py")),
        "tests/**/*.py": sorted(_TESTS.rglob("*.py")),
        "e2e/**/*.py": sorted(_E2E.rglob("*.py")),
    }


def _label(path: Path) -> str:
    """리포 기준 상대 경로 — 시험 파일 이름은 디렉터리마다 겹친다. 리포 밖이면 파일 이름."""
    try:
        return path.relative_to(_ROOT).as_posix()
    except ValueError:
        return path.name


def _judge() -> tuple[list[str], list[str]]:
    """(구문이 깨진 파일, fail-open 후보) — 네 표면을 한 번씩만 파싱한다."""
    broken, candidates = [], []
    cache: dict = {}
    for files in _scan_targets().values():
        for path in files:
            src = path.read_text(encoding="utf-8")
            try:
                tree = _parse(src)
            except SyntaxError:
                broken.append(_label(path))
                continue
            if (_reads_a_file(tree) and not _calls_structural_tool(tree, path, cache)
                    and not _has_escape_comment(src)):
                candidates.append(_label(path))
    return broken, candidates


def fail_open_candidates() -> list[str]:
    return _judge()[1]


def unparseable_files() -> list[str]:
    """네 표면에서 `ast.parse` 가 SyntaxError 를 내는 파일 — 실행되는 파일이라 구문 깨짐 = 결함이다.

    🔴 skip 하면 «파일은 있는데 분석 0개» 위에 ✅ 가 뜬다(파일 0개만 막고 분석 0개는 안 막음).
    Files whose ast.parse raises SyntaxError: a file that cannot parse cannot run.
    """
    return _judge()[0]


def main() -> int:
    # 🔴 빈 표면은 "통과" 가 아니라 glob/경로 붕괴다 — 표면 중 하나라도 0건이면 fail-closed.
    # An empty surface means the glob/path collapsed, not a pass.
    surfaces = _scan_targets()
    counts = " + ".join(f"{len(files)}개({label})" for label, files in surfaces.items())
    if any(not files for files in surfaces.values()):
        print(f"❌ 스캔 범위 붕괴 — {counts}")
        print("   빈 표면은 '위반 0건' 이 아니라 glob/경로가 무너졌다는 뜻이다(fail-closed).")
        return 1
    broken, candidates = _judge()
    if broken:
        print("❌ 구문 오류로 분석 불가한 파일 — 실행도 불가능한 상태다:")
        for b in broken:
            print(f"   - {b}")
        return 1
    if candidates:
        print("❌ 파일을 읽어 판정하나 구조 도구(ast · re · subprocess · 파서 입구 · 구조 헬퍼)를 하나도 안 부르는 파일:")
        for c in candidates:
            print(f"   - {c}")
        print("→ bare `X in text` 판정은 주석·docstring·산문이 통과시킨다(fail-open, #1136 클래스).")
        print("   구조를 읽을 것 — 템플릿·JS 는 `tests/unit/ui/_code_view.py`(있어야 할 것은 주석을 지운 본문,")
        print("   없어야 할 것은 원문) · 마이그레이션 SQL 은 `tests/unit/migrations/_migration_source.py` ·")
        print("   그 밖은 ast · 파서. 판정 대상이 정당하게 원문 글자 자체면")
        print(f"   `{_ESCAPE} <사유>` 주석으로 면제할 것.")
        return 1
    # 🔴 성공 문구는 **실제 스캔 범위**와 범위 밖을 적는다 — "가드 전부 통과" 처럼 읽히면 오독된다.
    # The banner names the exact scope and what lies outside it.
    print(f"✅ 스캔 {counts} — bare-substring fail-open 0")
    print("   범위 밖: 파이썬이 아닌 판정 코드(.claude/workflows/*.mjs · 셸) — 이 floor 는 파이썬 구문 트리만 읽는다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
