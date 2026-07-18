#!/usr/bin/env python3
"""PR-diff 한정 신규 noqa-은닉 미사용 import 가드 — self-inflicted CodeQL py/unused-import 차단.
PR-diff-scoped guard for new noqa-hidden unused imports — blocks self-inflicted CodeQL py/unused-import.

회고 2026-07-18 P1 테마 B: side-effect ORM import 에 `# noqa: F401` 을 달면 flake8(lint-changed-tests)
은 통과하나 CodeQL 은 별도 룰셋이라 main 전체 스캔에서 py/unused-import 로 노출 → 반응형 fix PR 반복
(#540~545, 본 창 3회). 이 가드는 PR diff 에서 **ADDED 된** noqa-은닉 import 만 차단해, 저자가 삭제하거나
튜플-참조 패턴(`_FK_TARGET_MODELS = (Model,)`; CodeQL 도 'used' 로 인식)으로 승격하도록 강제한다.
Retro 2026-07-18 P1 theme B: `# noqa: F401` on a side-effect ORM import passes flake8 but CodeQL still
flags py/unused-import post-merge, causing recurring reactive fix PRs. This blocks only NEW noqa-hidden
imports added in the diff, forcing removal or the tuple-reference pattern.

🔴 신규 diff 한정 (정책 17 안정성 우선): PR diff 의 **ADDED** 라인만 검사. 기존 ~115 legacy `# noqa: F401`
은 무관 — 2026-06-23 회고가 blanket 훅을 idiom churn 사유로 DROP 한 결정을 존중(신규 도입만 차단).
Diff-scoped: only ADDED lines are checked; legacy noqa imports are left untouched (respects the
2026-06-23 decision to avoid idiom churn — check_dual_import 선례).

사용법 / Usage: python scripts/check_noqa_sideeffect.py <base_sha> [head_sha]
  base 미지정 시 origin/main, head 미지정 시 HEAD. tests/ 하위 .py 만 대상(#979 lint-changed-tests 페어).
"""
import re
import subprocess
import sys

# import 문 여부 (import X / from X import Y). diff 의 `+` 는 사전에 제거하고 판정.
# Whether a line is an import statement (the leading diff `+` is stripped before checking).
_IMPORT = re.compile(r"^\s*(?:import\s|from\s+\S+\s+import\s)")
# `# noqa` (bare) 또는 `# noqa: <codes>` — codes 그룹(있으면) 캡처.
# `# noqa` (bare) or `# noqa: <codes>` — captures the codes group when present.
_NOQA = re.compile(r"#\s*noqa(?::\s*([A-Za-z0-9, ]+))?", re.IGNORECASE)
# diff ADDED 라인(`+...`) — `+++` 파일 헤더는 제외.
# A diff ADDED line (`+...`), excluding the `+++` file header.
_ADDED = re.compile(r"^\+(?!\+\+)")


def line_hides_f401(line):
    """import 라인이 F401 을 억제하는 noqa 를 달고 있으면 True.
    True if an import line carries a noqa that suppresses F401.

    - bare `# noqa`         → 전체 억제(F401 포함) → True
    - `# noqa: F401`        → True
    - `# noqa: E402,F401`   → True (목록에 F401)
    - `# noqa: E501`        → False (F401 미포함)
    - import 아닌 라인       → False
    """
    if not _IMPORT.match(line):
        return False
    m = _NOQA.search(line)
    if not m:
        return False
    codes = m.group(1)
    if codes is None:  # bare noqa — suppresses everything, incl. F401
        return True
    return "F401" in codes.upper().replace(" ", "").split(",")  # 정확 코드 매칭 / exact code match


def parse_added_noqa_imports(diff_text):
    """git diff 에서 ADDED(+) 된 noqa-은닉 import 라인 목록 반환(선행 `+` 제거).
    Return ADDED noqa-hidden import lines from a git diff (leading `+` stripped)."""
    out = []
    for raw in diff_text.splitlines():
        if not _ADDED.match(raw):
            continue
        line = raw[1:]  # strip leading '+'
        if line_hides_f401(line):
            out.append(line.strip())
    return out


def find_violations(path, diff_text):
    """파일 path 의 diff 에서 위반(ADDED noqa-은닉 import) 라인 목록.
    Violation lines (ADDED noqa-hidden imports) in the diff for `path`."""
    return parse_added_noqa_imports(diff_text)


def _git(args):
    """git 서브프로세스 — stdout 반환(실패 시 빈 문자열)."""
    out = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, encoding="utf-8"
    )
    return out.stdout or ""


def _changed_test_files(base, head):
    """base..head 에서 변경된 tests/ 하위 .py 목록.
    Changed tests/*.py between base and head."""
    names = _git(["diff", "--name-only", "--diff-filter=ACMR", base, head, "--", "tests/"])
    return [n for n in names.splitlines() if n.endswith(".py")]


def main(argv):
    base = argv[1] if len(argv) > 1 else "origin/main"
    head = argv[2] if len(argv) > 2 else "HEAD"
    violations = []
    for path in _changed_test_files(base, head):
        diff = _git(["diff", "-U0", base, head, "--", path])
        for line in find_violations(path, diff):
            violations.append((path, line))

    if not violations:
        print("✅ 신규 noqa-은닉 import 없음 / no new noqa-hidden imports")
        return 0

    print("🔴 신규 noqa-은닉 미사용 import 감지 — CodeQL py/unused-import 재발 위험 (회고 P1 테마 B):")
    print("   New noqa-hidden import(s) detected — self-inflicted CodeQL py/unused-import risk:")
    for path, line in violations:
        print(f"   - {path}: {line}")
    print()
    print("해결 / Fix: side-effect(등록용) import 는 `# noqa: F401` 대신 튜플-참조 패턴을 쓰세요.")
    print("  _FK_TARGET_MODELS = (Model,)  # CodeQL 도 'used' 로 인식 + import 소실 시 loud-fail")
    print("  (참조 / see: tests/unit/ui/test_repo_detail_query.py, alembic/env.py _REGISTERED_MODELS)")
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure
    sys.exit(main(sys.argv))
