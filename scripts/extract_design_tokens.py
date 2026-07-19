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

# CSS custom property 파싱 패턴 / CSS custom property parse pattern
_VAR_RE = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")

# 🔴 블록 수집은 반드시 `findall` — `search` 는 첫 블록만 잡는다.
#   tokens.css 에는 `:root` 가 **2개**, 테마별 plain 블록이 **2개씩** 있다(실측).
#   구 버전이 `re.search` 를 써서 174 선언 중 35 개만 산출하고도 exit 0 이었다.
# Collect with findall, never search: tokens.css has 2 `:root` blocks and 2 plain blocks per theme.
_ROOT_BLOCK_RE = re.compile(r":root\s*\{([^}]*)\}", re.DOTALL)

# 🔴 plain 테마 블록과 variant 블록을 **분리**한다 — 특이도가 다르다.
#   `[data-theme="dark"]`                        = (0,1,0)
#   `[data-theme="dark"][data-variant="signature"]` = (0,2,0)  ← 더 높다
#   variant 를 plain 에 last-wins 로 합치면 **variant 값이 기본값을 오염**시킨다
#   (variant 는 data-variant 속성이 있을 때만 적용되는데 항상 적용된 것처럼 보이게 된다).
# Keep variant blocks separate: their specificity is higher, so folding them into the base map
# would present variant-only values as the default.
_THEME_BLOCK_RE = re.compile(r'\[data-theme="([\w-]+)"\]\s*\{([^}]*)\}', re.DOTALL)
_VARIANT_BLOCK_RE = re.compile(
    r'\[data-theme="([\w-]+)"\]\[data-variant="([\w-]+)"\]\s*\{([^}]*)\}', re.DOTALL
)


def _strip_comments(css: str) -> str:
    """CSS 블록 주석 제거 (파싱 전처리) / Strip CSS block comments before parsing."""
    return re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)


def parse_vars(css_block: str) -> dict:
    """CSS 블록에서 custom property 추출 / Extract custom properties from CSS block."""
    return {f"--{m[0]}": m[1].strip() for m in _VAR_RE.findall(_strip_comments(css_block))}


def extract_theme_block(css: str, selector: str) -> dict:
    """특정 선택자 블록의 custom property 추출 / Extract vars from a specific selector block.

    🔴 호환 유지용 — 신규 경로는 `collect_themes()` 를 쓴다. 이 함수는 **첫 블록만** 보므로
    같은 선택자가 여러 번 나오는 현재 tokens.css 구조에는 부적합하다.
    Legacy helper (first block only); new code uses collect_themes().
    """
    clean_css = _strip_comments(css)
    pattern = re.compile(rf"{selector}[^{{]*\{{([^}}]+)\}}", re.DOTALL)
    m = pattern.search(clean_css)
    return parse_vars(m.group(1)) if m else {}


def collect_root(css_texts: list[str]) -> dict:
    """모든 `:root` 블록을 소스 순서로 병합 / Merge every `:root` block in source order.

    같은 특이도(0,0,0)의 규칙이므로 **뒤에 온 선언이 이긴다** = dict 갱신 순서와 일치.
    Equal specificity, so later declarations win — matching dict update order.
    """
    merged: dict = {}
    for text in css_texts:
        for body in _ROOT_BLOCK_RE.findall(_strip_comments(text)):
            merged.update(parse_vars(body))
    return merged


def collect_themes(css_texts: list[str]) -> tuple[dict, dict]:
    """테마별 plain 블록 병합 + variant 블록 분리 수집.
    Merge plain per-theme blocks; collect variant blocks separately.

    반환 / Returns: (themes, variants) — variants 는 `{"dark": {"signature": {...}}}` 형태.
    """
    themes: dict = {}
    variants: dict = {}
    for text in css_texts:
        clean = _strip_comments(text)
        # variant 를 먼저 걷어내야 plain 정규식이 variant 블록 본문을 삼키지 않는다.
        # Strip variant blocks first so the plain pattern cannot swallow their bodies.
        for theme, variant, body in _VARIANT_BLOCK_RE.findall(clean):
            variants.setdefault(theme, {}).setdefault(variant, {}).update(parse_vars(body))
        plain_removed = _VARIANT_BLOCK_RE.sub("", clean)
        for theme, body in _THEME_BLOCK_RE.findall(plain_removed):
            themes.setdefault(theme, {}).update(parse_vars(body))
    return themes, variants


def declared_names(css_texts: list[str]) -> set:
    """수집 대상 블록(`:root`·테마·variant)에 선언된 custom property 이름 전수.
    Every custom property declared in the inventoried blocks.

    🔴 완전성 관측자(`S ⊆ E`)의 좌변이다 — 파일 전체가 아니라 **우리가 읽기로 한 블록**만
    센다. 컴포넌트 선택자의 지역 변수는 디자인 토큰이 아니므로 대상 밖이다.
    Left-hand side of the completeness check; scoped to blocks we intend to read, not the
    whole file (component-local custom props are not design tokens).
    """
    names = set()
    for text in css_texts:
        clean = _strip_comments(text)
        bodies = list(_ROOT_BLOCK_RE.findall(clean))
        bodies += [b for _, b in _THEME_BLOCK_RE.findall(_VARIANT_BLOCK_RE.sub("", clean))]
        bodies += [b for _, _, b in _VARIANT_BLOCK_RE.findall(clean)]
        for body in bodies:
            names |= set(parse_vars(body))
    return names


def emitted_names(output: dict) -> set:
    """출력 JSON 에 실제로 실린 custom property 이름 전수 — `S ⊆ E` 의 우변."""
    names = set()
    for category in output.get("foundation", {}).values():
        names |= set(category)
    for theme in output.get("themes", {}).values():
        names |= set(theme)
    for variants in output.get("variants", {}).values():
        for block in variants.values():
            names |= set(block)
    return names


def categorize_root_vars(root_vars: dict) -> dict:
    """루트 변수를 카테고리별로 분류 / Categorize root variables by domain."""
    def filter_by_prefix(prefix_tuple):
        # startswith 기반 prefix 필터 (정확한 키 매칭 X) / prefix-based filter, not exact key match
        return {k: v for k, v in root_vars.items() if k.startswith(prefix_tuple)}

    categories = {
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
    # 🔴 어느 prefix 에도 안 맞는 토큰은 **버리지 않고** `other` 로 보낸다.
    #   구 버전은 조용히 드롭했다 — `:root` 를 전부 읽어도 `--font-sans` · `--density` ·
    #   `--lh-*` · `--ls-*` 등 14개가 사라졌다(실측). 블록 커버리지만 보는 관측자는
    #   이 손실을 통과시키므로, 드롭 자체를 없애는 것이 옳다.
    # Uncategorized tokens go to `other` instead of being dropped: the old version silently lost
    # 14 of them even when every :root block was read, and a block-coverage check would miss it.
    categorized = {k for cat in categories.values() for k in cat}
    categories["other"] = {k: v for k, v in root_vars.items() if k not in categorized}
    return categories


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

    # 🔴 두 파일을 함께 훑는다 — 테마 정의는 themes.css → tokens.css 로 이전됐고
    #   (themes.css 는 현재 compat stub), 되돌아가더라도 이 수집이 깨지지 않는다.
    # Scan both files: theme definitions moved from themes.css (now a stub) into tokens.css.
    sources = [tokens_text, themes_text]

    themes, variants = collect_themes(sources)
    output = {
        "foundation": categorize_root_vars(collect_root(sources)),
        "themes": themes,
        "variants": variants,
    }

    # 🔴 완전성 관측자 — 수집 대상 블록에 선언된 이름은 **전부** 출력에 실려야 한다(S ⊆ E).
    #   구 버전은 174 선언 중 35 개만 쓰고도 성공 메시지를 찍고 exit 0 했다. 관측 없는 추출기는
    #   조용히 열화하며, 그 산출물로 디자인 결정이 내려진다. 임의 하한(magic floor)은 썩으므로
    #   집합 포함 관계로 단언한다.
    # Completeness observer: every declared name must reach the output. The old version emitted
    # 35 of 174 and still exited 0. No magic floor — set containment, which cannot rot.
    missing = sorted(declared_names(sources) - emitted_names(output))
    if missing:
        print(f"ERROR: {len(missing)} declared tokens missing from output: {missing[:15]}")
        sys.exit(1)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    # 🔴 개행으로 끝내야 pre-commit `end-of-file-fixer` 가 매 재생성마다 커밋을 되돌리지 않는다.
    # Trailing newline so the end-of-file-fixer hook does not abort every regeneration commit.
    OUTPUT.write_text(
        json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    total = len(emitted_names(output))
    print(f"Tokens extracted → {OUTPUT}")
    print(f"    foundation categories: {list(output['foundation'].keys())}")
    print(f"    themes: {list(output['themes'].keys())}")
    print(f"    variants: { {t: list(v) for t, v in output['variants'].items()} }")
    print(f"    unique token names: {total}")


if __name__ == "__main__":
    main()
