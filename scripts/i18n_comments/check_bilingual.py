#!/usr/bin/env python3
"""
Bilingual comment validator for SCAManager.
한글 주석에 영어 번역이 병행 작성되었는지 검증한다.
Validates that Korean comments have English translations alongside them.

Usage / 사용법:
    python scripts/i18n_comments/check_bilingual.py [path ...] [--strict] [--report]

    --strict   : 미번역 라인 발견 시 exit code 1 반환 (CI 게이트용)
                 Exit code 1 if untranslated lines are found (CI gate mode)
    --report   : 파일별 진행률 요약 출력
                 Print per-file progress summary
    path       : 검사할 파일 또는 디렉토리 (기본값: src/ tests/ e2e/)
                 Files or directories to check (default: src/ tests/ e2e/)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 한글 유니코드 범위 (가-힣, 자모, 호환 자모)
# Korean Unicode ranges (Hangul syllables, Jamo, Compatibility Jamo)
KOREAN_RE = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")

# 4글자 이상 영문 단어 — mixed 라인 판정에 사용
# 4+ letter English word — used to classify a line as already bilingual
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]{4,}")

# "한글 / English" 인라인 슬래시 패턴 (이미 병행 작성된 인라인 주석)
# Inline slash bilingual pattern already applied: # 한글 / English
SLASH_BILINGUAL_RE = re.compile(r"#[^#\n]*[가-힣][^#\n]*/\s*[A-Za-z]")

# 주석 라인 여부 판정 패턴
# Pattern to detect comment-only lines (not inline trailing comments)
COMMENT_LINE_RE = re.compile(r"^\s*#")

# EXCLUDE: 번역 정책 대상이 아닌 경로
# EXCLUDE: paths outside translation policy scope
EXCLUDE_DIRS = {
    ".claude",
    "alembic/versions",
    "alembic\\versions",
    "docs",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".git",
    "review_guides",  # LLM review checklist content — not developer comments
}
EXCLUDE_FILES = {
    "review_prompt.py",  # LLM prompt strings — score regression risk
}


def _is_excluded(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    if any(ex in path_str for ex in EXCLUDE_DIRS):
        return True
    return path.name in EXCLUDE_FILES


def _collect_py_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            if root.suffix == ".py" and not _is_excluded(root):
                files.append(root)
        else:
            for p in sorted(root.rglob("*.py")):
                if not _is_excluded(p):
                    files.append(p)
    return files


def _has_korean(line: str) -> bool:
    return bool(KOREAN_RE.search(line))


def _has_english(text: str) -> bool:
    return bool(ENGLISH_WORD_RE.search(text))


def _is_comment_or_docstring_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")


def _korean_ratio(text: str) -> float:
    if not text:
        return 0.0
    korean = sum(1 for ch in text if KOREAN_RE.match(ch))
    return korean / len(text)


def _adj_has_english_comment(adj: str, indent: int) -> bool:
    adj_indent = len(adj) - len(adj.lstrip())
    if adj_indent != indent or not COMMENT_LINE_RE.match(adj):
        return False
    adj_body = adj.strip().lstrip("#").strip()
    return bool(adj_body and not _has_korean(adj_body) and _has_english(adj_body))


def _adj_has_english_content(adj: str) -> bool:
    adj_body = adj.strip().lstrip("#").strip()
    return bool(adj_body and not _has_korean(adj_body) and _has_english(adj_body))


def _line_is_mixed_bilingual(line: str) -> bool:
    stripped = line.strip().lstrip("#").strip().strip('"').strip("'")
    if not _has_english(stripped):
        return False
    if stripped.startswith(("noqa", "pylint")):
        return False
    return _korean_ratio(stripped) < 0.5


def _is_already_bilingual(line: str, prev_line: str, next_line: str) -> bool:
    """
    영어 번역이 이미 존재하는지 판단한다.
    Returns True if English translation already exists alongside the Korean line.

    판정 기준 (any of):
    Decision criteria (any of):
    1. 인라인 슬래시 패턴: # 한글 / English
    2. 인접 # 주석 라인에 같은 들여쓰기의 영문이 존재
    3. docstring 오프너일 때 인접 연속 줄에 영문 존재
    4. 라인 자체가 한글 비율 50% 미만 (mixed bilingual)
    """
    if SLASH_BILINGUAL_RE.search(line):
        return True

    indent = len(line) - len(line.lstrip())
    is_docstring_opener = line.strip().startswith(('"""', "'''"))

    for adj in (prev_line, next_line):
        if not adj:
            continue
        if _adj_has_english_comment(adj, indent):
            return True
        if is_docstring_opener and _adj_has_english_content(adj):
            return True

    return _line_is_mixed_bilingual(line)


def check_file(path: Path) -> tuple[int, int]:
    """
    파일 내 한글 주석 라인 수와 미번역 라인 수를 반환한다.
    Returns (total_korean_comment_lines, untranslated_lines) for the file.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return 0, 0

    total = 0
    untranslated = 0

    for i, line in enumerate(lines):
        if not _has_korean(line):
            continue
        if not _is_comment_or_docstring_line(line):
            continue

        total += 1
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1] if i < len(lines) - 1 else ""

        if not _is_already_bilingual(line, prev_line, next_line):
            untranslated += 1

    return total, untranslated


def _print_progress(grand_total: int, grand_untranslated: int, file_results: list, base: Path) -> None:
    translated = grand_total - grand_untranslated
    pct = (translated / grand_total * 100) if grand_total else 100.0
    print("=== Bilingual Comment Progress ===")
    print(f"Files with Korean: {len(file_results)}")
    print(f"Korean comment lines: {grand_total}")
    print(f"Translated: {translated}  Remaining: {grand_untranslated}")
    print(f"Progress: {pct:.1f}%")

    remaining = [(f, t, u) for f, t, u in file_results if u > 0]
    if remaining:
        print("\n--- Files with untranslated lines ---")
        remaining.sort(key=lambda x: -x[2])
        for f, total, unt in remaining[:40]:
            rel = str(f).replace(str(base) + "\\", "").replace(str(base) + "/", "")
            pct_f = ((total - unt) / total * 100) if total else 100
            print(f"  {rel}: {unt} untranslated / {total} total ({pct_f:.0f}% done)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bilingual comment validator")
    parser.add_argument("paths", nargs="*", default=["src", "tests", "e2e"],
                        help="Files or directories to check")
    parser.add_argument("--strict", action="store_true",
                        help="Exit code 1 if untranslated lines found")
    parser.add_argument("--report", action="store_true",
                        help="Print per-file progress summary")
    parser.add_argument("--phase", type=int, default=None,
                        help="Filter report to phase files only (informational)")
    args = parser.parse_args()

    base = Path("f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager")
    roots = [base / p for p in args.paths]
    files = _collect_py_files(roots)

    grand_total = 0
    grand_untranslated = 0
    file_results: list[tuple[Path, int, int]] = []

    for f in files:
        total, untranslated = check_file(f)
        if total > 0:
            grand_total += total
            grand_untranslated += untranslated
            file_results.append((f, total, untranslated))

    if args.report or args.strict:
        _print_progress(grand_total, grand_untranslated, file_results, base)

    if args.strict and grand_untranslated > 0:
        print(f"\n[FAIL] {grand_untranslated} untranslated Korean comment lines remain.",
              file=sys.stderr)
        return 1

    if not args.report and not args.strict:
        translated = grand_total - grand_untranslated
        pct = (translated / grand_total * 100) if grand_total else 100.0
        print(f"Progress: {translated}/{grand_total} ({pct:.1f}%) — {grand_untranslated} remaining")

    return 0


if __name__ == "__main__":
    sys.exit(main())
