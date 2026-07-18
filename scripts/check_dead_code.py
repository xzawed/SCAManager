#!/usr/bin/env python3
"""PR-diff 한정 신규 dead-code 가드 — 호출자 0 공개 repository/service 함수 차단.
PR-diff-scoped dead-code guard — blocks new public repository/service functions with no in-src caller.

회고 2026-07-18 P1#9/14/15: #1060 `find_orphaned` 가 호출자 0 dead code 로 13 PR 생존(전 스위트
green + 5+1 + opus whole-branch 미검출, #1073 이 뒤늦게 배선). service 함수의 mutation-green 이
route/caller 배선을 못 잡는 구조 갭. 이 가드는 PR diff 에서 ADDED 된 src/repositories·src/services 의
**공개** 함수가 src/ 어디서도 AST 참조되지 않으면 차단한다.
Retro 2026-07-18 P1#9/14/15: find_orphaned survived 13 PRs as zero-caller dead code (all gates green).
This blocks NEW public repository/service functions that have no in-src AST reference.

🔴 AST 참조 카운트 (docstring/주석 제외) — grep 은 자기 docstring 멘션에 false-negative.
AST reference counting excludes docstring/comment mentions (grep false-negatives on self-mentions).

🔴 신규 diff 한정 (정책 17 안정성) — 기존 함수 무관, ADDED 공개 함수만 검사.
🔴 의도적 미배선 예외: 같은 diff 에 `# unwired-ok: <name> (사유·후속 PR)` 마커 추가 시 skip(이월 추적).
Intentional staging: add `# unwired-ok: <name> (reason/follow-up PR)` in the same diff to skip.

사용법 / Usage: python scripts/check_dead_code.py <base_sha> [head_sha]
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

# 검사 대상 디렉토리 — 호출자 배선 누락이 dead code 로 남는 계층(회고 P1#9/14/15).
# Scoped dirs — the layers where a missing caller leaves dead code.
_SCOPED_DIRS = ("src/repositories/", "src/services/")

# ADDED(+) `def`/`async def` 라인의 함수명. 공개(비-underscore)만.
# Function name on an ADDED `def`/`async def` line; public (non-underscore) only.
_ADDED_DEF = re.compile(r"^\+\s*(?:async\s+)?def\s+([A-Za-z][A-Za-z0-9_]*)\s*\(")
# `# unwired-ok: <name>` 마커(ADDED 라인) — 의도적 미배선 예외.
# `# unwired-ok: <name>` marker on an ADDED line — intentional-staging exception.
_UNWIRED_OK = re.compile(r"#\s*unwired-ok:\s*([A-Za-z_][A-Za-z0-9_]*)")
_ADDED = re.compile(r"^\+(?!\+\+)")


def parse_added_public_defs(diff_text):
    """diff 의 ADDED 라인에서 공개 함수 def 이름 집합(underscore 제외).
    Public function names from ADDED `def` lines in the diff (underscore excluded)."""
    out = set()
    for raw in diff_text.splitlines():
        m = _ADDED_DEF.match(raw)
        if m and not m.group(1).startswith("_"):
            out.add(m.group(1))
    return out


def parse_unwired_ok_names(diff_text):
    """diff 의 ADDED `# unwired-ok: <name>` 마커 함수명 집합.
    Names marked `# unwired-ok: <name>` on ADDED lines in the diff."""
    out = set()
    for raw in diff_text.splitlines():
        if not _ADDED.match(raw):
            continue
        for m in _UNWIRED_OK.finditer(raw):
            out.add(m.group(1))
    return out


def count_ast_references(name, source):
    """source(파이썬 코드)에서 name 에 대한 AST 참조 수 — Name(id) + Attribute(attr).
    Count AST references to `name` in `source` — ast.Name(id=) + ast.Attribute(attr=).

    🔴 def 문의 이름·docstring·주석·문자열은 참조 아님(파싱 노드 아니거나 str 리터럴).
    The def-statement name, docstrings, comments, and string literals are NOT references."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return 0
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            count += 1
        elif isinstance(node, ast.Attribute) and node.attr == name:
            count += 1
    return count


def _git(args):
    """git 서브프로세스 → stdout. 실패 시 **loud 종료**(fail-CLOSED).

    🔴 **PARITY GUARD** — 동일 구현이 `check_noqa_sideeffect.py`·`check_dual_import.py` 에도
    있다. 한 곳을 고치면 셋 다 고쳐야 한다(`tests/unit/scripts/test_guard_git_failclosed.py`
    가 동작 동등성 강제).
    🔴 fail-OPEN 금지 (회고 2026-07-19 P1): 구 구현은 실패 시 `""` 를 반환해 "결과 없음 =
    ✅ 위반 없음 + exit 0" 으로 귀결됐다 — 잘못된 base SHA·shallow clone 에서 가드가 조용히
    무력화되고 로그에는 성공 배너만 남았다.
    Fail-closed git helper; duplicated in two sibling guards (parity enforced by test).
    """
    out = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, encoding="utf-8"
    )
    if out.returncode != 0:
        print(f"🔴 git 실패 — 가드 실행 불가 (fail-closed): git {' '.join(args)}")
        print(f"   {(out.stderr or '').strip()[:300]}")
        sys.exit(2)
    return out.stdout or ""


def _changed_scoped_files(base, head):
    """base..head 에서 변경된 repositories/services .py 목록.
    Changed repositories/services .py files between base and head."""
    names = _git(["diff", "--name-only", "--diff-filter=ACMR", base, head, "--", *_SCOPED_DIRS])
    return [n for n in names.splitlines() if n.endswith(".py")]


def _total_references(name, src_root):
    """src/ 전체 .py 에서 name 의 AST 참조 총합.
    Total AST references to `name` across all src/*.py."""
    total = 0
    for py in src_root.rglob("*.py"):
        total += count_ast_references(name, py.read_text(encoding="utf-8", errors="replace"))
    return total


def main(argv):
    base = argv[1] if len(argv) > 1 else "origin/main"
    head = argv[2] if len(argv) > 2 else "HEAD"

    # 변경된 scoped 파일들의 ADDED 공개 def + unwired-ok 마커 수집.
    # Collect ADDED public defs + unwired-ok markers across changed scoped files.
    candidates, whitelisted = set(), set()
    for path in _changed_scoped_files(base, head):
        diff = _git(["diff", "-U0", base, head, "--", path])
        candidates |= parse_added_public_defs(diff)
        whitelisted |= parse_unwired_ok_names(diff)
    candidates -= whitelisted

    if not candidates:
        print("✅ 신규 dead-code 후보 없음 / no new dead-code candidates")
        return 0

    src_root = Path("src")
    dead = sorted(n for n in candidates if _total_references(n, src_root) == 0)
    if not dead:
        print(f"✅ 신규 공개 함수 {len(candidates)}개 모두 src 내 호출자 有 / all wired")
        return 0

    print("🔴 신규 공개 repository/service 함수가 src 내 호출자 0 (declared-but-unwired 회고 P1#9/14/15):")
    print("   New public repository/service function(s) with no in-src caller:")
    for n in dead:
        print(f"   - {n}()")
    print()
    print("해결 / Fix: (a) 호출부를 배선하거나 (b) 의도적 미배선이면 diff 에 마커를 추가하세요:")
    print("   # unwired-ok: <name> (사유·후속 배선 PR 번호)")
    print("   (참조 / see: #1060 find_orphaned 가 호출자 0 로 13 PR 생존 → #1073 뒤늦은 배선)")
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure
    sys.exit(main(sys.argv))
