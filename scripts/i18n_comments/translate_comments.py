#!/usr/bin/env python3
"""
Bilingual comment translator for SCAManager.
한글 주석에 영어 번역을 병행 삽입한다.
Inserts English translations alongside Korean comments using Claude Haiku 4.5.

Usage / 사용법:
    python scripts/i18n_comments/translate_comments.py [path ...] [options]

Options:
    --dry-run    : 파일을 수정하지 않고 변경 예정 내용만 출력
                   Print planned changes without modifying files
    --batch      : 배치 모드 — 모든 대상 파일 순차 처리
                   Process all target files sequentially
    --phase N    : Phase N 대상 파일만 처리
                   Process only Phase N target files
    --force      : manifest SHA 무관하게 재처리 (멱등성 우회)
                   Reprocess even if file SHA matches manifest (bypass idempotency)
    path         : 처리할 파일 또는 디렉토리
                   Files or directories to process

Environment:
    ANTHROPIC_API_KEY  : Claude API 키 (필수)
                         Required for translation
    BYPASS_AUTO_TEST=1 : PostToolUse Hook 자동 pytest 비활성화 힌트 (Hook 수동 설정 필요)
                         Hint to suppress auto-test hook (requires manual hook config)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path("f:/DEVELOPMENT/SOURCE/CLAUDE/SCAManager")
MANIFEST_PATH = BASE_DIR / "scripts" / "i18n_comments" / "manifest.json"
GLOSSARY_PATH = BASE_DIR / "scripts" / "i18n_comments" / "glossary.md"

# 한글 유니코드 범위
# Korean Unicode ranges
KOREAN_RE = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]{4,}")
SLASH_BILINGUAL_RE = re.compile(r"#[^#\n]*[가-힣][^#\n]*/\s*[A-Za-z]")
COMMENT_LINE_RE = re.compile(r"^\s*#")

# 번역 정책 제외 파일
# Files excluded from translation policy
EXCLUDE_FILES = {"review_prompt.py"}
EXCLUDE_DIRS_STR = {".claude", "alembic/versions", "alembic\\versions", "docs", "__pycache__"}

# Phase별 파일 목록 (우선순위 순)
# Phase file mapping (priority order)
PHASE_FILES: dict[int, list[str]] = {
    1: [
        "src/constants.py",
        "src/config.py",
        "src/database.py",
        "src/main.py",
        "alembic/env.py",
    ],
    2: [
        "src/github_client/repos.py",
        "src/gate/engine.py",
        "src/worker/pipeline.py",
        "src/notifier/github_comment.py",
        "src/notifier/telegram.py",
        "src/shared/merge_metrics.py",
        "src/shared/claude_metrics.py",
        "src/analyzer/io/tools/golangci_lint.py",
        "src/analyzer/io/ai_review.py",
        "src/shared/observability.py",
        "src/analyzer/io/tools/slither.py",
        "src/api/hook.py",
        "src/notifier/github_issue.py",
        "src/cli/formatter.py",
        "src/notifier/email.py",
        "src/gate/merge_reasons.py",
        "src/gate/merge_failure_advisor.py",
        "src/gate/github_review.py",
        "src/shared/stage_metrics.py",
        "src/analyzer/pure/review_guides/__init__.py",
    ],
}

# 글로사리를 system prompt에 포함 (prompt caching 활용)
# Glossary is included in system prompt (leverages prompt caching)
SYSTEM_PROMPT = """You are a precise bilingual comment translator for the SCAManager project.
SCAManager is a GitHub PR/Push automated code quality analysis and AI review service using Claude AI.

TASK:
Given a JSON list of Korean comment or docstring lines (with line numbers), return a JSON object
mapping each line number to its English translation.

STRICT RULES:
1. Translate ONLY the Korean text. Keep code, symbols (#, \"\"\", ''', variable names) unchanged.
2. Use the domain glossary below — do NOT substitute synonyms.
3. Match the tone: concise technical English (not verbose, no "This function...").
4. For inline comments with "# 한글", output only the translated text (no leading #).
5. For docstrings, preserve paragraph structure.
6. Do NOT translate: variable names, file paths, URLs, error codes, tool names (pylint, bandit, etc.).
7. Output: JSON only — {"line_number": "english translation", ...}. No explanation.

DOMAIN GLOSSARY (mandatory):
- 점수 → score (not point/mark)
- 등급 → grade
- 감점 → deduction (not penalty)
- 게이트/Gate → gate (PR Gate)
- 자동 머지 → auto merge
- 멱등성 → idempotency
- 임계값 → threshold
- 알림 채널 → notification channel
- 관측/계측 → observability
- 정적 분석 → static analysis
- 파이프라인 → pipeline
- 서명 검증 → signature verification
- 배점 → max score / weight
- 구현 방향성 → implementation direction
- 멱등성 보장 → idempotency guard
- 병렬 실행 → parallel execution
- 스케일링 → scaling
- 반자동 → semi-auto
- 승인/반려 → approve/reject
- 헬스체크 → health check
- Fallback → fallback
- 캐시 → cache
"""


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_excluded(path: Path) -> bool:
    path_str = str(path).replace("\\", "/")
    for ex in EXCLUDE_DIRS_STR:
        if ex.replace("\\", "/") in path_str:
            return True
    return path.name in EXCLUDE_FILES


def _has_korean(line: str) -> bool:
    return bool(KOREAN_RE.search(line))


def _is_already_bilingual(line: str, prev_line: str, next_line: str) -> bool:
    if SLASH_BILINGUAL_RE.search(line):
        return True
    indent = len(line) - len(line.lstrip())
    for adj in (prev_line, next_line):
        if not adj:
            continue
        adj_indent = len(adj) - len(adj.lstrip())
        if adj_indent == indent and COMMENT_LINE_RE.match(adj):
            adj_stripped = adj.strip().lstrip("#").strip()
            if adj_stripped and not KOREAN_RE.search(adj_stripped) and ENGLISH_WORD_RE.search(adj_stripped):
                return True
    stripped = line.strip().lstrip("#").strip().strip('"').strip("'")
    if ENGLISH_WORD_RE.search(stripped) and not KOREAN_RE.search(stripped.replace(stripped[:stripped.find(" ")+1] if " " in stripped else stripped, "")):
        if sum(1 for ch in stripped if KOREAN_RE.match(ch)) / max(len(stripped), 1) < 0.5:
            return True
    return False


def _is_comment_or_docstring_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")


def _collect_translatable_lines(lines: list[str]) -> dict[int, str]:
    """
    번역이 필요한 라인 번호(1-indexed)와 원본 텍스트를 반환한다.
    Returns {line_number: line_text} for lines that need translation.
    """
    result: dict[int, str] = {}
    for i, line in enumerate(lines):
        if not _has_korean(line):
            continue
        if not _is_comment_or_docstring_line(line):
            continue
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1] if i < len(lines) - 1 else ""
        if not _is_already_bilingual(line, prev_line, next_line):
            result[i + 1] = line  # 1-indexed
    return result


def _build_api_input(translatable: dict[int, str]) -> list[dict]:
    items = []
    for lineno, text in translatable.items():
        stripped = text.strip()
        if stripped.startswith("#"):
            comment_text = stripped.lstrip("#").strip()
        else:
            comment_text = stripped.strip('"""').strip("'''").strip()
        items.append({"line": lineno, "korean": comment_text, "raw": text})
    return items


def _call_claude_api(items: list[dict], client: anthropic.Anthropic) -> dict[int, str]:
    """
    Claude Haiku 4.5를 호출하여 번역 결과를 반환한다.
    Calls Claude Haiku 4.5 and returns {line_number: english_translation}.
    """
    if not items:
        return {}

    user_content = json.dumps(
        [{"line": it["line"], "korean": it["korean"]} for it in items],
        ensure_ascii=False, indent=2
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_content}],
            )
            raw = response.content[0].text.strip()
            if raw.startswith("```"):
                raw = re.sub(r"```(?:json)?\n?", "", raw).rstrip("`").strip()
            translations = json.loads(raw)
            return {int(k): v for k, v in translations.items()}
        except (json.JSONDecodeError, anthropic.APIError) as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"  [WARN] Claude API error after {max_retries} attempts: {e}", file=sys.stderr)
            return {}


def _apply_translations(lines: list[str], translations: dict[int, str], translatable: dict[int, str]) -> list[str]:
    """
    번역 결과를 원본 라인 목록에 삽입한다.
    Inserts English translations into the original lines list.

    포맷 규칙:
    Format rules:
    - 인라인 주석 (x = 1  # 한글): "# 한글 / English" 슬래시 패턴
      Inline comment: slash pattern
    - 단독 라인 주석 (# 한글): 다음 줄에 # English 추가
      Standalone comment: insert # English on next line
    - docstring 줄: 다음 줄에 들여쓰기 맞춰 # English 추가 (최소 개입)
      Docstring line: insert # English indented on next line
    """
    result = list(lines)
    # 역순으로 삽입해야 라인 번호가 유지된다
    # Insert in reverse order to preserve line numbers
    insert_offset = 0
    for lineno in sorted(translations.keys()):
        eng = translations[lineno]
        if not eng:
            continue
        idx = lineno - 1 + insert_offset
        original = result[idx]

        indent = len(original) - len(original.lstrip())
        stripped = original.strip()

        is_inline = not stripped.startswith("#") or (
            not stripped.startswith("# ") and "  #" in original
        )
        # 인라인 주석 판별: 코드가 앞에 오는 경우
        # Inline detection: code precedes the comment
        code_part = original[:original.rfind("#")] if "#" in original else ""
        is_inline = bool(code_part.strip())

        if is_inline:
            # "# 한글 / English" 슬래시 패턴
            comment_start = original.rfind("#")
            prefix = original[:comment_start]
            comment_body = original[comment_start:].strip().lstrip("#").strip()
            # 라인 길이 120 초과 시 두 줄 분리
            # Split to two lines if 120 char limit exceeded
            new_inline = f"{prefix}# {comment_body} / {eng}"
            if len(new_inline) <= 120:
                result[idx] = new_inline + ("\n" if original.endswith("\n") else "")
            else:
                # 두 줄 분리
                eng_line = " " * indent + f"# {eng}"
                result[idx] = original.rstrip("\n") + "\n"
                result.insert(idx + 1, eng_line + "\n")
                insert_offset += 1
        elif stripped.startswith("#"):
            # 단독 라인 주석: 다음 줄에 삽입
            # Standalone comment: insert on next line
            eng_line = " " * indent + f"# {eng}"
            result.insert(idx + 1, eng_line + "\n")
            insert_offset += 1
        else:
            # docstring 내용 라인
            # Docstring content line
            eng_line = " " * indent + f"# {eng}"
            result.insert(idx + 1, eng_line + "\n")
            insert_offset += 1

    return result


def process_file(path: Path, client: anthropic.Anthropic, dry_run: bool = False, force: bool = False) -> bool:
    """
    파일 한 개를 처리한다. 변경 발생 시 True 반환.
    Processes a single file. Returns True if changes were made.
    """
    manifest = _load_manifest()
    rel_path = str(path).replace(str(BASE_DIR) + "\\", "").replace(str(BASE_DIR) + "/", "")
    sha = _file_sha256(path)

    if not force and manifest.get(rel_path, {}).get("sha") == sha:
        print(f"  [SKIP] {rel_path} — unchanged (manifest hit)")
        return False

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"  [ERROR] Cannot read {rel_path}: {e}", file=sys.stderr)
        return False

    lines = content.splitlines(keepends=True)
    translatable = _collect_translatable_lines([l.rstrip("\n") for l in lines])

    if not translatable:
        print(f"  [OK] {rel_path} — already bilingual or no Korean comments")
        manifest[rel_path] = {"sha": sha, "status": "done"}
        if not dry_run:
            _save_manifest(manifest)
        return False

    print(f"  [TRANSLATE] {rel_path} — {len(translatable)} lines to translate")
    items = _build_api_input(translatable)

    if dry_run:
        print(f"    (dry-run) Would call Claude API for {len(items)} lines")
        for it in items[:5]:
            print(f"    L{it['line']}: {it['korean'][:60]}")
        if len(items) > 5:
            print(f"    ... and {len(items) - 5} more")
        return False

    translations = _call_claude_api(items, client)
    if not translations:
        print(f"  [WARN] No translations returned for {rel_path}", file=sys.stderr)
        return False

    new_lines = _apply_translations([l.rstrip("\n") for l in lines], translations, translatable)
    new_content = "\n".join(new_lines)
    if not new_content.endswith("\n"):
        new_content += "\n"

    if new_content == content:
        print(f"  [NO-CHANGE] {rel_path}")
        return False

    path.write_text(new_content, encoding="utf-8")
    new_sha = _file_sha256(path)
    manifest[rel_path] = {"sha": new_sha, "status": "done"}
    _save_manifest(manifest)
    print(f"  [DONE] {rel_path} — {len(translations)} translations applied")
    return True


def _collect_phase_files(phase: int) -> list[Path]:
    files = PHASE_FILES.get(phase, [])
    return [BASE_DIR / f for f in files if (BASE_DIR / f).exists()]


def _collect_files(paths: list[str]) -> list[Path]:
    result: list[Path] = []
    for p in paths:
        target = BASE_DIR / p if not Path(p).is_absolute() else Path(p)
        if target.is_file():
            if target.suffix == ".py" and not _is_excluded(target):
                result.append(target)
        elif target.is_dir():
            for f in sorted(target.rglob("*.py")):
                if not _is_excluded(f):
                    result.append(f)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Bilingual comment translator")
    parser.add_argument("paths", nargs="*", help="Files or directories to process")
    parser.add_argument("--dry-run", action="store_true", help="No file modification")
    parser.add_argument("--batch", action="store_true", help="Process all target files")
    parser.add_argument("--phase", type=int, default=None, help="Process Phase N files only")
    parser.add_argument("--force", action="store_true", help="Bypass manifest SHA check")
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key and not args.dry_run:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 1

    client = anthropic.Anthropic(api_key=api_key) if api_key else None

    # 처리 대상 파일 목록 결정
    # Determine target file list
    if args.phase is not None:
        files = _collect_phase_files(args.phase)
        print(f"Phase {args.phase}: {len(files)} files")
    elif args.paths:
        files = _collect_files(args.paths)
    elif args.batch:
        files = _collect_files(["src", "tests", "e2e"])
    else:
        parser.print_help()
        return 0

    changed = 0
    for f in files:
        if _is_excluded(f):
            continue
        if client or args.dry_run:
            if process_file(f, client, dry_run=args.dry_run, force=args.force):
                changed += 1
        time.sleep(0.1)  # API 레이트 리밋 완화 / Reduce API rate limit pressure

    print(f"\nSummary: {changed}/{len(files)} files changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
