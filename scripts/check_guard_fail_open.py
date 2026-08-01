#!/usr/bin/env python3
"""가드(scripts/check_*.py)의 **fail-open 저술 floor 게이트** — write-time (backlog B8).

## 배경 (2026-07-20 Grok 최종 적대검증)

이 저장소 최다 반복 실수 = observer-lie(가드가 산문/echo 로 통과). 문서 재구성은 규율을
AGENTS.md·guards.md 로 옮기고 **불변식 3(배선)만** 기계화했으나, **불변식 1(fail-closed:
통과가 산문으로 충족되면 안 됨)의 write-time 게이트는 없었다** — fail-open 저술은 여전히
review 에서만 잡혔다(#1136 echo · #1156 대기). Grok: "rate-limiting step 미변".

## 🔴 이 게이트가 하는 것 (floor — 완전 탐지기 아님, 정직히)

**파일을 읽어 pass/fail 을 판정하는 check 가드가 구조 분석 도구(ast·re·subprocess)를 하나도
안 쓰면 = fail-open 후보로 차단.** bare `X in file_text` 만으로 판정하는 가드(#1136 클래스)를
저술 시점에 잡는다.

🔴 **한계 (감추지 않음)**: 이건 **floor 이지 천장이 아니다**. 구조 도구를 import 하고도 **결정
자체는 bare substring** 으로 하는 가드는 이 게이트를 통과한다(Grok 이 원한 "결정 표현식 AST
분석" 은 더 강하고 어렵다 — 오탐 위험). 그 강한 버전은 backlog B8 잔여로 남긴다. 여기서는
가장 egregious 한 "구조 도구 0" 케이스만 확실히 막는다.

## 자기 3-불변식 적용 (이 게이트도 관측자다)

- fail-closed: 도구 사용을 **AST 호출 관측**으로 판정(import·주석 언급이 아니라 실제 `ast.`/
  `re.`/`subprocess.` **호출**). 산문이 통과시킬 수 없다.
- 실경로 뮤테이션: 회귀 테스트가 합성 bare-substring 가드 → 차단 실증.
- 배선: pre-commit + CI. `test_guard_wiring_coverage` 가 배선 강제.

escape hatch: 정당한 substring-only 가드는 `# fail-open-reviewed: <사유>` 주석으로 면제.
"""
import ast
import io
import sys
import tokenize
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
# 🔴 훅 표면도 스캔한다 (backlog R16 — R6 이 "B8 이 .claude/hooks/** 미검" 을 적발).
#    실측(2026-08-02): 현 훅 4종 전부 구조 도구 사용 = 오탐 0 확인 후 확대.
# Scan the hook surface too (backlog R16; R6 flagged the gap). Measured zero false
# positives on the four existing hooks before widening.
_HOOKS = _ROOT / ".claude" / "hooks"

_ESCAPE = "# fail-open-reviewed:"
# 구조 분석 도구 — 이 중 하나라도 **호출**하면 bare-substring 이 아니다.
_STRUCTURAL_MODULES = {"ast", "re", "subprocess"}


def _reads_a_file(tree: ast.AST) -> bool:
    """파일을 읽는가 — `.read_text(...)`/`.read_bytes(...)` 또는 `open(...)` 호출.

    🔴 `read_bytes` 포함 (Grok claim-review `019fbe1f` GROK-20260802-2 재현 적발) —
    bytes 로 읽어 decode 후 bare substring 판정하는 가드가 이름 집합 밖이라 미탐이었다.
    Includes read_bytes: a guard reading bytes then substring-deciding escaped the name set.
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
            if name in ("read_text", "read_bytes", "open", "read"):
                return True
    return False


def _structural_import_names(tree: ast.AST) -> tuple[set, set]:
    """구조 도구를 가리키는 이름을 import 에서 해소 — alias·from-import 인정.

    🔴 `import re as r` / `from re import search` 를 못 보면 정당한 가드를 fail-open 오탐한다.
    Resolve names that point at a structural tool, honoring aliases and from-imports.
    Returns (module_aliases, direct_names): `<alias>.attr(...)` 용 alias 집합 + `search(...)` 용 bare 명.
    """
    module_aliases = set()  # `import re as r` → {"r"}; `import re` → {"re"}
    direct_names = set()    # `from re import search as s` → {"s"}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name in _STRUCTURAL_MODULES:
                    module_aliases.add(a.asname or a.name)
        elif isinstance(n, ast.ImportFrom):
            if n.module in _STRUCTURAL_MODULES:
                for a in n.names:
                    direct_names.add(a.asname or a.name)
    return module_aliases, direct_names


def _calls_structural_tool(tree: ast.AST) -> bool:
    """실제로 **호출**되는 구조 분석 도구가 있는가 — `re.search(...)`·`r.search(...)`·`search(...)`.

    🔴 import·주석 언급이 아니라 `<alias>.<attr>(...)` 호출 또는 from-import 된 이름 호출을 본다
    (산문 통과 방지). alias·from-import 를 해소해 정당한 가드 오탐도 막는다.
    """
    module_aliases, direct_names = _structural_import_names(tree)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        func = n.func
        # <alias>.attr(...) — 예: re.search / r.search
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.value.id in module_aliases:
                return True
        # from-import 된 함수 호출 — 예: search(...)
        if isinstance(func, ast.Name) and func.id in direct_names:
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


def _scan_targets() -> tuple[list[Path], list[Path]]:
    """스캔 표면 2종 — `scripts/check_*.py` + `.claude/hooks/*.py`.

    표면별로 따로 반환한다 — main() 이 **표면별 붕괴**(glob 0건)를 구별해 fail-closed 하기 위함.
    Two scan surfaces, returned separately so main() can fail closed per-surface on collapse.
    """
    return sorted(_SCRIPTS.glob("check_*.py")), sorted(_HOOKS.glob("*.py"))


def fail_open_candidates() -> list[str]:
    out = []
    scripts, hooks = _scan_targets()
    for path in scripts + hooks:
        src = path.read_text(encoding="utf-8")
        if _has_escape_comment(src):
            continue  # 명시 면제 (실제 주석 토큰에 한함)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            # 구문 깨짐은 별도 축(`unparseable_files`)이 main 에서 exit 1 로 승격한다 —
            # 여기서의 skip 이 조용한 미탐이 되지 않게 한다(GROK-20260802-1).
            # Broken syntax is escalated to exit 1 by `unparseable_files` in main, so this
            # skip can no longer become a silent miss.
            continue
        if _reads_a_file(tree) and not _calls_structural_tool(tree):
            out.append(path.name)
    return out


def unparseable_files() -> list[str]:
    """양 표면에서 `ast.parse` 가 SyntaxError 를 내는 파일명 목록.

    🔴 Grok claim-review `019fbe1f` GROK-20260802-1 재현 적발 — 표면에 파일이 있어도
    **전부 구문 깨짐**이면 후보 skip 으로 ✅ exit 0 이었다("파일 0개" 만 막고 "분석 0개" 는
    안 막음). scripts/hooks 는 실행돼야 하는 파일이라 구문 깨짐 = 실행 불가능한 가드 = 결함
    (오탐 0 — 정당하게 파싱 불가한 파일이 이 표면에 있을 수 없다).
    Files whose ast.parse raises SyntaxError. A guard that cannot parse cannot run — that is
    a defect, not a skip (zero false positives on these surfaces).
    """
    scripts, hooks = _scan_targets()
    broken = []
    for path in scripts + hooks:
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            broken.append(path.name)
    return broken


def main() -> int:
    # 🔴 빈 표면은 "통과" 가 아니라 glob/경로 붕괴다 (backlog R16 — 뮤테이션 GROK-9:
    #    범위를 비워도 ✅ 성공 문구가 나왔다). 표면 중 하나라도 0건이면 fail-closed.
    # An empty surface means the glob/path collapsed, not a pass (mutation GROK-9 measured
    # a green banner over an empty scope). Fail closed if either surface scans zero files.
    scripts, hooks = _scan_targets()
    if not scripts or not hooks:
        print(f"❌ 스캔 범위 붕괴 — scripts/check_*.py {len(scripts)}개 · "
              f".claude/hooks/*.py {len(hooks)}개")
        print("   빈 표면은 '위반 0건' 이 아니라 glob/경로가 무너졌다는 뜻이다(fail-closed).")
        return 1
    # 🔴 구문 깨진 파일은 skip 이 아니라 실패다 (GROK-20260802-1 — 전부 깨져도 ✅ 이던 미탐).
    # A syntax-broken file is a failure, not a skip (all-broken surfaces used to pass green).
    broken = unparseable_files()
    if broken:
        print("❌ 구문 오류로 분석 불가한 가드/훅 파일 — 실행도 불가능한 상태다:")
        for b in broken:
            print(f"   - {b}")
        return 1
    candidates = fail_open_candidates()
    if candidates:
        print("❌ 파일을 읽어 판정하나 구조 분석 도구(ast/re/subprocess)를 하나도 안 쓰는 가드:")
        for c in candidates:
            print(f"   - {c}")
        print("→ bare `X in text` substring 판정은 산문/echo 가 통과시킨다(fail-open, #1136 클래스).")
        print("   ast.parse/re.search/subprocess 로 **구조**를 보거나, 정당하면")
        print(f"   `{_ESCAPE} <사유>` 주석으로 면제할 것.")
        return 1
    # 🔴 성공 문구는 **실제 스캔 범위**를 명시한다 (backlog R16) — "가드 전부 통과" 처럼 읽히면
    #    범위 밖(test-as-guard)의 fail-open 까지 덮은 것으로 오독된다.
    # The banner names the exact scope; a generic "all guards pass" would be read as covering
    # the test-as-guard surface this floor cannot see.
    print(f"✅ 스캔 {len(scripts)}개(scripts/check_*.py) + {len(hooks)}개(.claude/hooks/*.py) — "
          "bare-substring fail-open 0")
    print("   범위 밖: tests/** test-as-guard 표면 — write-time 규율(guards.md) + "
          "review-time claim-review 로만 방어된다(B8 floor 한계).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
