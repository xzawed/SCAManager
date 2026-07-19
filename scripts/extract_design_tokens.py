#!/usr/bin/env python3
"""
tokens.css / themes.css 를 파싱해 Claude Design 입력용 JSON 생성.
Parses tokens.css / themes.css and outputs structured JSON for Claude Design.

사용법 / Usage:
    python scripts/extract_design_tokens.py
출력 / Output:
    docs/design/brief/01-current-tokens.json
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKENS_CSS = ROOT / "src" / "static" / "css" / "tokens.css"
THEMES_CSS = ROOT / "src" / "static" / "css" / "themes.css"
OUTPUT = ROOT / "docs" / "design" / "brief" / "01-current-tokens.json"

# 테마 선택자 매핑 / Theme selector mapping
THEME_SELECTORS = {
    "dark": r'body\[data-theme="dark"\]',
    "light": r'body\[data-theme="light"\]',
    "pastel": r'body\[data-theme="pastel"\]',
    "catppuccin": r'body\[data-theme="catppuccin"\]',
}

# CSS custom property 파싱 패턴 / CSS custom property parse pattern
_VAR_RE = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")


def _strip_comments(css: str) -> str:
    """CSS 블록 주석 제거 (파싱 전처리) / Strip CSS block comments before parsing."""
    return re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)


def parse_vars(css_block: str) -> dict:
    """CSS 블록에서 custom property 추출 / Extract custom properties from CSS block."""
    return {f"--{m[0]}": m[1].strip() for m in _VAR_RE.findall(_strip_comments(css_block))}


def extract_theme_block(css: str, selector: str) -> dict:
    """특정 선택자 블록의 custom property 추출 / Extract vars from a specific selector block."""
    clean_css = _strip_comments(css)
    pattern = re.compile(rf"{selector}[^{{]*\{{([^}}]+)\}}", re.DOTALL)
    m = pattern.search(clean_css)
    return parse_vars(m.group(1)) if m else {}


def categorize_root_vars(root_vars: dict) -> dict:
    """루트 변수를 카테고리별로 분류 / Categorize root variables by domain."""
    def filter_by_prefix(prefix_tuple):
        # startswith 기반 prefix 필터 (정확한 키 매칭 X) / prefix-based filter, not exact key match
        return {k: v for k, v in root_vars.items() if k.startswith(prefix_tuple)}

    return {
        "spacing": filter_by_prefix("--space-"),
        "typography": filter_by_prefix(("--fs-xs", "--fs-sm", "--fs-md", "--fs-base",
                             "--fs-lg", "--fs-xl", "--fs-2xl", "--fs-3xl")),
        "display_typography": filter_by_prefix(("--fs-display", "--tracking-", "--line-height-display")),
        "radius": filter_by_prefix("--radius-"),
        "elevation": filter_by_prefix("--elev-"),
        "motion": filter_by_prefix(("--dur-", "--ease-", "--anim-")),
        "blur": filter_by_prefix("--blur-"),
        "container": filter_by_prefix("--container-"),
        "grade_colors": filter_by_prefix("--grade-"),
        "claude_brand": filter_by_prefix("--claude-"),
    }


def _make_stdout_safe():
    """Windows cp949 stdout 에서 이모지/한글 출력 크래시 방지 — UTF-8 재구성(errors=replace).
    Guard against the cp949 emoji/Korean print crash on Windows (UTF-8, replace on miss).

    🔴 standalone 실행(`python scripts/x.py`)이라 공유 헬퍼를 import 할 수 없다 — scripts/ 에
    패키지 초기화가 없어 sys.path 조작이 필요해지므로, 검증된 관용구를 각 스크립트에
    복제한다(정책 16 최소 추상화). 누락 방지는 회귀 가드가 담당:
    `tests/unit/scripts/test_stdout_encoding_guard.py`.
    Scripts run standalone, so the idiom is duplicated rather than imported; a regression guard
    asserts no script is left unguarded.
    """
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass  # 캡처된 stream 등 reconfigure 미지원 — 무시 / stream without reconfigure


def main() -> None:
    """메인 진입점 / Main entry point."""
    _make_stdout_safe()
    # 실제 CSS 파일 파싱 / Parse actual CSS files
    tokens_text = TOKENS_CSS.read_text(encoding="utf-8")
    themes_text = THEMES_CSS.read_text(encoding="utf-8")

    # :root 블록 추출 / Extract :root block
    root_m = re.search(r":root\s*\{([^}]+)\}", tokens_text, re.DOTALL)
    root_vars = parse_vars(root_m.group(1)) if root_m else {}

    output = {
        "foundation": categorize_root_vars(root_vars),
        "themes": {
            name: extract_theme_block(themes_text, sel)
            for name, sel in THEME_SELECTORS.items()
        },
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Tokens extracted → {OUTPUT}")
    print(f"    foundation categories: {list(output['foundation'].keys())}")
    print(f"    themes: {list(output['themes'].keys())}")


if __name__ == "__main__":
    main()
