#!/usr/bin/env python3
"""
메모리 슬러그 교차 점검 스크립트.
Memory slug cross-checker script.

CLAUDE.md / .claude/policies/active.md / history.md 에서 참조된 메모리 슬러그와
실제 메모리 디렉토리 파일 목록을 비교해 누락·스테일 어노테이션·미참조 파일을 보고한다.

Compares memory slugs referenced in project docs against actual files in the memory
directory, reporting: missing files, stale "(현재 미생성)" annotations, unreferenced files.
"""
import io
import re
import sys
from pathlib import Path

# Windows cp949 환경에서 한글/이모지 출력 오류 방지
# Prevent encoding errors on Windows cp949 for Korean/emoji output.
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

MEMORY_DIR = (
    Path.home() / ".claude" / "projects" / "d--Source-SCAManager" / "memory"
)
DOC_FILES = [
    "CLAUDE.md",
    ".claude/policies/active.md",
    ".claude/policies/history.md",
]
SLUG_PATTERN = re.compile(r"`((?:feedback|project|user)-[\w-]+\.md)`")
STALE_PATTERN = re.compile(
    r"`((?:feedback|project|user)-[\w-]+\.md)`\s*\(현재 미생성[^)]*\)"
)


def collect_referenced(project_root: Path) -> dict[str, list[str]]:
    """각 문서에서 메모리 슬러그 참조를 수집한다. / Collect memory slug references from each doc."""
    referenced: dict[str, list[str]] = {}
    for rel_path in DOC_FILES:
        full_path = project_root / rel_path
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding="utf-8")
        for match in SLUG_PATTERN.finditer(content):
            referenced.setdefault(match.group(1), []).append(rel_path)
    return referenced


def collect_stale(project_root: Path, actual: set[str]) -> list[tuple[str, str]]:
    """파일은 생성됐으나 '(현재 미생성)' 어노테이션이 잔존하는 항목 탐지.
    Detect slugs where the file exists but a '(현재 미생성)' annotation still remains."""
    stale: list[tuple[str, str]] = []
    for rel_path in DOC_FILES:
        full_path = project_root / rel_path
        if not full_path.exists():
            continue
        content = full_path.read_text(encoding="utf-8")
        for match in STALE_PATTERN.finditer(content):
            slug = match.group(1)
            if slug in actual:
                stale.append((rel_path, slug))
    return stale


def print_report(
    referenced: dict[str, list[str]],
    actual: set[str],
    stale: list[tuple[str, str]],
) -> bool:
    """결과를 출력하고 문제가 없으면 True를 반환한다. / Print report; return True when clean."""
    missing = {slug for slug in referenced if slug not in actual}
    extra = actual - set(referenced.keys())

    print("=== SCAManager 메모리 슬러그 점검 / Memory Slug Check ===\n")
    print(f"참조된 슬러그: {len(referenced)}개")
    print(f"실제 파일:     {len(actual)}개")

    ok = True

    if missing:
        ok = False
        print(f"\n❌ 누락 파일 ({len(missing)}개 — 문서 참조 O, 파일 X):")
        for slug in sorted(missing):
            refs = ", ".join(referenced[slug])
            print(f"  {slug}  ← {refs}")
    else:
        print("\n✅ 모든 참조 슬러그에 실제 파일 존재")

    if stale:
        ok = False
        print(f"\n⚠️  스테일 어노테이션 ({len(stale)}건 — 파일 생성 후 '(현재 미생성)' 잔존):")
        for doc, slug in stale:
            print(f"  {doc}: `{slug}` (현재 미생성) → 어노테이션 제거 필요")
    else:
        print("✅ 스테일 '(현재 미생성)' 어노테이션 없음")

    if extra:
        print(f"\nℹ️  미참조 파일 ({len(extra)}개 — 문서 참조 X, 파일 O):")
        for slug in sorted(extra):
            print(f"  {slug}")

    return ok


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]

    if not MEMORY_DIR.exists():
        print(f"❌ 메모리 디렉토리 없음: {MEMORY_DIR}")
        return 1

    referenced = collect_referenced(project_root)
    actual = {f.name for f in MEMORY_DIR.glob("*.md") if f.name != "MEMORY.md"}
    stale = collect_stale(project_root, actual)

    return 0 if print_report(referenced, actual, stale) else 1


if __name__ == "__main__":
    sys.exit(main())
