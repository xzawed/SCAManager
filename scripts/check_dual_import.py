#!/usr/bin/env python3
"""PR-diff 한정 신규 이중 import 가드 — CodeQL py/import-and-import-from self-inflict 차단.
PR-diff-scoped new dual-import guard — blocks self-inflicted CodeQL py/import-and-import-from.

회고 2026-07-03 C2: #1021 N2 테스트가 `from src.config import Settings` 를 추가해 기존
`import src.config as cfg` 와 공존 → CodeQL `py/import-and-import-from`(#538/#539) 자초 → #1023 봉인.
flake8 F401/F841(#979)·noqa 는 이 패턴을 원리상 미검출(양쪽 import 모두 used).
Retro 2026-07-03 C2: a test added `from src.config import Settings` alongside an existing
`import src.config as cfg`, self-inflicting CodeQL py/import-and-import-from → sealed by #1023.
flake8 F401/F841 cannot detect it (both imports are used).

🔴 신규 diff 한정 (정책 17 안정성 우선): PR diff 에서 **ADDED 된** `from X import` 만 검사한다.
기존 28 legacy idiom(`import X as mock` + `from X import fn`)은 무관 — 2026-06-23 회고가 전면
pre-commit 훅(WF-1)을 idiom churn 사유로 DROP 한 결정을 존중 (신규 도입만 차단, 기존 미churn).
Only NEW `from X import` lines added in the diff are checked; legacy idioms are left untouched
(respects the 2026-06-23 decision to DROP a blanket pre-commit hook to avoid idiom churn).

사용법 / Usage: python scripts/check_dual_import.py <base_sha> [head_sha]
  base 미지정 시 origin/main, head 미지정 시 HEAD. tests/ 하위 .py 만 대상(#979 lint-changed-tests 페어).
"""
import re
import subprocess
import sys

# diff -U0 의 ADDED 라인(`+from x import ...`) 에서 모듈명 추출 (`+++` 헤더는 제외).
# Extract module from an added `+from x import ...` line in `git diff -U0` (excludes `+++` header).
_ADDED_FROM_IMPORT = re.compile(r"^\+\s*from\s+([\w.]+)\s+import\b")


def parse_added_from_modules(diff_text: str) -> set[str]:
    """diff -U0 텍스트에서 ADDED 된 `from <mod> import` 의 <mod> 집합 반환 (순수 함수).
    Return the set of <mod> for `from <mod> import` lines added in a `git diff -U0` text."""
    mods: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("+++"):  # diff 파일 헤더 — 스킵 / diff file header — skip
            continue
        match = _ADDED_FROM_IMPORT.match(line)
        if match:
            mods.add(match.group(1))
    return mods


def content_has_plain_import(content: str, module: str) -> bool:
    """파일 내용에 `import <module>` (plain 또는 `as alias`) 존재 여부 (순수 함수).
    Whether the content has an `import <module>` (plain or `as alias`) statement."""
    pattern = re.compile(
        rf"^\s*import\s+{re.escape(module)}(\s+as\s+\w+)?\s*(#.*)?$", re.MULTILINE
    )
    return bool(pattern.search(content))


def find_violations_for_file(diff_text: str, head_content: str) -> list[str]:
    """한 파일의 diff + 최종 내용에서 신규 이중 import 를 유발하는 모듈 목록 (순수 함수).
    Modules that introduce a new dual-import for one file (added `from`, coexisting plain `import`)."""
    return sorted(
        mod
        for mod in parse_added_from_modules(diff_text)
        if content_has_plain_import(head_content, mod)
    )


def _git(*args: str) -> str:
    """git 명령 실행 → stdout. 실패 시 **loud 종료**(fail-CLOSED).

    🔴 **PARITY GUARD** — 동일 구현이 `check_dead_code.py`·`check_noqa_sideeffect.py` 에도
    있다. 한 곳을 고치면 셋 다 고쳐야 한다(`tests/unit/scripts/test_guard_git_failclosed.py`).
    🔴 fail-OPEN 금지 (회고 2026-07-19 P1): 구 구현의 `""` 반환은 "✅ 위반 없음 + exit 0" 으로
    귀결돼 git 실패가 곧 가드 무력화였다.
    Fail-closed git helper; duplicated in two sibling guards (parity enforced by test).
    """
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"🔴 git 실패 — 가드 실행 불가 (fail-closed): git {' '.join(args)}")
        print(f"   {(result.stderr or '').strip()[:300]}")
        sys.exit(2)
    return result.stdout or ""


def find_violations(base: str, head: str) -> list[tuple[str, str]]:
    """PR-changed tests/ .py 전체에서 (파일, 모듈) 위반 목록 (git I/O).
    All (file, module) violations across PR-changed tests/ .py files."""
    names = _git("diff", "--name-only", "--diff-filter=ACMR", base, head, "--", "tests/")
    violations: list[tuple[str, str]] = []
    for path in (p for p in names.splitlines() if p.endswith(".py")):
        diff_text = _git("diff", "-U0", base, head, "--", path)
        head_content = _git("show", f"{head}:{path}")
        for mod in find_violations_for_file(diff_text, head_content):
            violations.append((path, mod))
    return violations


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 standalone 실행(`python scripts/x.py`)이라 공유 헬퍼를 import 할 수 없다 —
    scripts/ 에 패키지 초기화가 없어 sys.path 조작이 필요해지므로, 검증된 4줄 관용구를
    각 스크립트에 복제한다(정책 16 최소 추상화). 누락 방지는 회귀 가드가 담당:
    `tests/unit/scripts/test_stdout_encoding_guard.py`.
    Scripts run standalone, so the idiom is duplicated rather than imported; a regression
    guard asserts no script is left unguarded.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def main(argv: list[str]) -> int:
    """CLI 진입점 — 위반 시 사유 출력 후 exit 1, 없으면 exit 0 (CI 게이트).
    CLI entry point — print violations and exit 1, else exit 0 (CI gate)."""
    _make_stdout_safe()
    base = argv[1] if len(argv) > 1 else "origin/main"
    head = argv[2] if len(argv) > 2 else "HEAD"
    violations = find_violations(base, head)
    if violations:
        print("🔴 신규 이중 import 감지 (CodeQL py/import-and-import-from 자초 위험):")
        print("🔴 New dual-import detected (self-inflicted CodeQL py/import-and-import-from risk):")
        for path, mod in violations:
            print(
                f"  {path}: 신규 `from {mod} import ...` 가 기존 `import {mod}` 와 공존 "
                f"→ 하나로 통일 (testing.md '모듈 패치 시 이중 import 회피 — string-path 우선')"
            )
        return 1
    print("신규 이중 import 없음 — OK / no new dual-import — OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
