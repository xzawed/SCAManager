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


def parse_vars(css_block: str) -> dict:
    """CSS 블록에서 custom property 추출 / Extract custom properties from CSS block."""
    return {f"--{m[0]}": m[1].strip() for m in _VAR_RE.findall(css_block)}


def extract_theme_block(css: str, selector: str) -> dict:
    """특정 선택자 블록의 custom property 추출 / Extract vars from a specific selector block."""
    pattern = re.compile(rf"{selector}[^{{]*\{{([^}}]+)\}}", re.DOTALL)
    m = pattern.search(css)
    return parse_vars(m.group(1)) if m else {}


def categorize_root_vars(root_vars: dict) -> dict:
    """루트 변수를 카테고리별로 분류 / Categorize root variables by domain."""
    def pick(prefix_tuple):
        # 접두사 매칭으로 관련 변수 필터링 / Filter variables by prefix match
        return {k: v for k, v in root_vars.items() if k.startswith(prefix_tuple)}

    return {
        "spacing": pick("--space-"),
        "typography": pick(("--fs-xs", "--fs-sm", "--fs-md", "--fs-base",
                             "--fs-lg", "--fs-xl", "--fs-2xl", "--fs-3xl")),
        "display_typography": pick(("--fs-display", "--tracking-", "--line-height-display")),
        "radius": pick("--radius-"),
        "elevation": pick("--elev-"),
        "motion": pick(("--dur-", "--ease-", "--anim-")),
        "blur": pick("--blur-"),
        "container": pick("--container-"),
        "grade_colors": pick("--grade-"),
        "claude_brand": pick("--claude-"),
    }


def main() -> None:
    """메인 진입점 / Main entry point."""
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
