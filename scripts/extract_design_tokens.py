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

# 🔴 아래 3종은 **놓치고 있던 스코프**다 (2026-07-19 회고 P1 — 8블록 12선언 무음 누락).
#   구 구현은 `:root` · `[data-theme="X"]` · 테마별 variant 만 봤고, 그 결과
#   `--border`·`--text-muted`·`--text-subtle` 3개 이름이 통째로 사라졌으며
#   density/radius **모드별 값**은 값 자체가 산출물에 없었다(디자인 브리프가 밀도 시스템을 못 봄).
# Three scopes the old implementation never read — 8 blocks / 12 declarations silently dropped.

# 테마 공유 기본값: `[data-theme] { ... }` (값 없는 속성 선택자).
#   🔴 `[data-theme="X"]` 와 특이도가 같고(0,1,0) **소스상 뒤에 온다** → 겹치면 이쪽이 이긴다.
#   현재 겹치는 키는 0개(실측)라 테마에 병합해도 무손실이다. 겹치면 가드가 CI 에서 막는다.
_SHARED_THEME_RE = re.compile(r'(?<![\]"\w])\[data-theme\]\s*\{([^}]*)\}', re.DOTALL)

# 테마 무관 variant: `[data-variant="signature"] { ... }` (테마 접두 없음).
_BARE_VARIANT_RE = re.compile(r'(?<![\]"\w])\[data-variant="([\w-]+)"\]\s*\{([^}]*)\}', re.DOTALL)

# 모디파이어 스코프: `[data-density="compact"]` · `[data-radius="soft"]` 등.
#   밀도/모서리는 **디자인 시스템의 축**이므로 브리프에 실려야 한다.
_MODIFIER_RE = re.compile(
    r'(?<![\]"\w])\[data-(density|radius)="([\w-]+)"\]\s*\{([^}]*)\}', re.DOTALL
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

    반환 / Returns: (themes, variants, shared, modifiers)
      · themes    — 테마별 실효값(공유 기본값 병합 완료)
      · variants  — `{"dark": {"signature": {...}}}` · 테마 무관은 키 `"*"`
      · shared    — `[data-theme]` 원본(병합 전) — 출처 추적용
      · modifiers — `{"density": {"compact": {...}}, "radius": {...}}`
    """
    themes: dict = {}
    variants: dict = {}
    shared: dict = {}
    modifiers: dict = {}
    for text in css_texts:
        clean = _strip_comments(text)
        # variant 를 먼저 걷어내야 plain 정규식이 variant 블록 본문을 삼키지 않는다.
        # Strip variant blocks first so the plain pattern cannot swallow their bodies.
        for theme, variant, body in _VARIANT_BLOCK_RE.findall(clean):
            variants.setdefault(theme, {}).setdefault(variant, {}).update(parse_vars(body))
        plain_removed = _VARIANT_BLOCK_RE.sub("", clean)
        for theme, body in _THEME_BLOCK_RE.findall(plain_removed):
            themes.setdefault(theme, {}).update(parse_vars(body))
        # 테마 공유 기본값 / 테마 무관 variant / 모디파이어 — 구 구현이 놓치던 3 스코프
        for body in _SHARED_THEME_RE.findall(clean):
            shared.update(parse_vars(body))
        for variant, body in _BARE_VARIANT_RE.findall(plain_removed):
            variants.setdefault("*", {}).setdefault(variant, {}).update(parse_vars(body))
        for axis, mode, body in _MODIFIER_RE.findall(clean):
            modifiers.setdefault(axis, {}).setdefault(mode, {}).update(parse_vars(body))

    # 🔴 공유 기본값을 각 테마에 병합 — "dark 는 무엇인가" 에 답하는 **실효값** 스냅샷이다.
    #   `[data-theme]` 는 `[data-theme="X"]` 와 동일 특이도이고 소스상 뒤에 오므로 겹치면 이긴다.
    #   현재 겹치는 키 0개(실측)라 무손실. 겹치기 시작하면 아래 가드가 CI 에서 막는다.
    # Merge shared defaults into each theme (effective values). Equal specificity, later in source.
    collision = {k for k in shared for t in themes.values() if k in t}
    if collision:
        raise ValueError(
            f"`[data-theme]` 공유 키가 테마별 키와 충돌한다: {sorted(collision)}\n"
            "→ 병합 순서가 값에 영향을 준다. 어느 쪽이 실효값인지 명시적으로 결정할 것."
        )
    for theme_map in themes.values():
        theme_map.update(shared)
    return themes, variants, shared, modifiers


def declared_names(css_texts: list[str]) -> set:
    """소스 파일에 선언된 custom property 이름 **전수** — 구현과 **독립** 산출.

    Every custom property declared in the source files — computed independently of extraction.

    🔴 이것이 완전성 관측자(`S ⊆ E`)의 좌변이고, **구현과 같은 정규식을 쓰면 안 된다**.
    구 구현은 좌변을 `_ROOT_BLOCK_RE`·`_THEME_BLOCK_RE`·`_VARIANT_BLOCK_RE` 로 만들었다 —
    즉 **추출이 못 읽는 블록은 좌변에서도 안 보여** `S ⊆ E` 가 공허하게 참이었다.
    실측 결과 그 상태로 174 중 171 만 산출하면서 "완전" 을 보고하고 있었다.

    지금은 **블록 구조를 전혀 모르는 dumb 스캔**을 쓴다 — 선택자·중괄호를 파싱하지 않고
    `--이름:` 패턴만 센다. 그래서 새로운 선택자 형태가 생기면 좌변에는 즉시 나타나고
    우변(추출)에는 안 나타나 **관측자가 실패한다**.

    🔴 allowlist 를 두지 않는 이유: 이 두 파일(`tokens.css`·`themes.css`)은 **정의상
    디자인 토큰 파일**이다. 컴포넌트 지역 변수는 `components.css` 등 다른 파일에 있으므로
    여기서 제외할 것이 없다. 예외 목록은 그 자체가 도피처가 된다.
    The left side uses a deliberately dumb scan that knows nothing about block structure, so a
    new selector shape shows up here but not in the extraction — making the observer fail.
    """
    names = set()
    for text in css_texts:
        names |= set(re.findall(r"--[\w-]+(?=\s*:)", _strip_comments(text)))
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
    names |= set(output.get("theme_shared", {}))
    for axis in output.get("modifiers", {}).values():
        for block in axis.values():
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

    themes, variants, shared, modifiers = collect_themes(sources)
    output = {
        "foundation": categorize_root_vars(collect_root(sources)),
        "themes": themes,
        "theme_shared": shared,
        "variants": variants,
        "modifiers": modifiers,
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
    print(f"    theme_shared: {len(output['theme_shared'])}개")
    print(f"    modifiers: { {a: list(m) for a, m in output['modifiers'].items()} }")
    print(f"    unique token names: {total}")


if __name__ == "__main__":
    main()
