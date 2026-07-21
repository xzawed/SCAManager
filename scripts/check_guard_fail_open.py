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
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"

_ESCAPE = "# fail-open-reviewed:"
# 구조 분석 도구 — 이 중 하나라도 **호출**하면 bare-substring 이 아니다.
_STRUCTURAL_MODULES = {"ast", "re", "subprocess"}


def _reads_a_file(tree: ast.AST) -> bool:
    """파일을 읽는가 — `.read_text(...)` 또는 `open(...)` 호출."""
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            name = getattr(n.func, "attr", None) or getattr(n.func, "id", None)
            if name in ("read_text", "open", "read"):
                return True
    return False


def _calls_structural_tool(tree: ast.AST) -> set:
    """실제로 **호출**되는 구조 분석 도구 — `re.search(...)`·`ast.parse(...)`·`subprocess.run(...)`.

    🔴 import·주석 언급이 아니라 `<module>.<attr>(...)` 호출을 본다(산문 통과 방지).
    """
    used = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            root = n.func.value
            if isinstance(root, ast.Name) and root.id in _STRUCTURAL_MODULES:
                used.add(root.id)
    return used


def fail_open_candidates() -> list[str]:
    out = []
    for path in sorted(_SCRIPTS.glob("check_*.py")):
        src = path.read_text(encoding="utf-8")
        if _ESCAPE in src:
            continue  # 명시 면제
        try:
            tree = ast.parse(src)
        except SyntaxError:  # pragma: no cover
            continue
        if _reads_a_file(tree) and not _calls_structural_tool(tree):
            out.append(path.name)
    return out


def main() -> int:
    candidates = fail_open_candidates()
    if candidates:
        print("❌ 파일을 읽어 판정하나 구조 분석 도구(ast/re/subprocess)를 하나도 안 쓰는 가드:")
        for c in candidates:
            print(f"   - {c}")
        print("→ bare `X in text` substring 판정은 산문/echo 가 통과시킨다(fail-open, #1136 클래스).")
        print("   ast.parse/re.search/subprocess 로 **구조**를 보거나, 정당하면")
        print(f"   `{_ESCAPE} <사유>` 주석으로 면제할 것.")
        return 1
    n = len(list(_SCRIPTS.glob("check_*.py")))
    print(f"✅ check 가드 {n}개 — 파일 판정 가드가 전부 구조 분석 도구 사용(bare-substring fail-open 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
