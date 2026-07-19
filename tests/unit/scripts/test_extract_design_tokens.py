"""
토큰 추출 스크립트 단위 테스트.
Unit tests for the design token extraction script.
"""
import re
import json
import textwrap
from pathlib import Path

# 스크립트 임포트 경로 설정 / Script import path setup
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from extract_design_tokens import parse_vars, extract_theme_block, categorize_root_vars


SAMPLE_ROOT_CSS = textwrap.dedent("""
    :root {
      --space-1: 4px;
      --space-2: 8px;
      --fs-xs: 12px;
      --fs-sm: 13px;
      --radius-sm: 6px;
      --elev-0: none;
      --dur-fast: 120ms;
      --blur-sm: 8px;
      --container-lg: 1200px;
      --fs-display-sm: 32px;
      --tracking-tight: -0.02em;
    }
""")

SAMPLE_THEMES_CSS = textwrap.dedent("""
    body[data-theme="dark"], body:not([data-theme]) {
      --bg-base: #07070f;
      --accent: #6366f1;
      --text-1: #f0f0f8;
    }

    body[data-theme="light"] {
      --bg-base: #f6f6fd;
      --accent: #6366f1;
      --text-1: #0f0f1a;
    }
""")


def test_parse_vars_extracts_all_custom_properties():
    css = ":root { --space-1: 4px; --fs-xs: 12px; }"
    result = parse_vars(css)
    assert result == {"--space-1": "4px", "--fs-xs": "12px"}


def test_parse_vars_trims_whitespace():
    css = ":root { --color:   #fff  ; }"
    result = parse_vars(css)
    assert result["--color"] == "#fff"


def test_extract_theme_block_dark():
    result = extract_theme_block(SAMPLE_THEMES_CSS, r'body\[data-theme="dark"\]')
    assert result["--bg-base"] == "#07070f"
    assert result["--accent"] == "#6366f1"


def test_extract_theme_block_light():
    result = extract_theme_block(SAMPLE_THEMES_CSS, r'body\[data-theme="light"\]')
    assert result["--bg-base"] == "#f6f6fd"
    assert result["--text-1"] == "#0f0f1a"


def test_extract_theme_block_missing_returns_empty():
    result = extract_theme_block(SAMPLE_THEMES_CSS, r'body\[data-theme="pastel"\]')
    assert result == {}


def test_categorize_root_vars_spacing():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--space-1" in categories["spacing"]
    assert "--space-2" in categories["spacing"]


def test_categorize_root_vars_typography():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--fs-xs" in categories["typography"]
    assert "--fs-sm" in categories["typography"]


def test_categorize_root_vars_display_typography():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--fs-display-sm" in categories["display_typography"]
    assert "--tracking-tight" in categories["display_typography"]


def test_categorize_root_vars_elevation():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--elev-0" in categories["elevation"]


def test_categorize_root_vars_motion():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--dur-fast" in categories["motion"]


def test_categorize_root_vars_radius():
    root_vars = parse_vars(SAMPLE_ROOT_CSS)
    categories = categorize_root_vars(root_vars)
    assert "--radius-sm" in categories["radius"]


def test_parse_vars_ignores_css_comments():
    """CSS 주석 내 변수 패턴이 실제 값을 오염시키지 않는지 확인 / Verify CSS comments do not corrupt actual values."""
    css = textwrap.dedent("""
        /* --elev-0: 평면 / --elev-1~4: 단계적 깊이 */
        --elev-0: none;
        --elev-1: 0 1px 2px rgba(0,0,0,.04);
    """)
    result = parse_vars(css)
    assert result["--elev-0"] == "none"
    assert "--elev-1" in result
    # 주석 내용이 값으로 추출되어선 안 됨 / comment content must not appear as a value
    assert "평면" not in result.get("--elev-0", "")


def test_main_generates_valid_json(tmp_path, monkeypatch):
    """main() 실제 CSS 파일 파싱 후 올바른 JSON 생성 확인 / Verify main() generates valid JSON."""
    import extract_design_tokens as mod

    output_file = tmp_path / "tokens.json"
    monkeypatch.setattr(mod, "OUTPUT", output_file)
    mod.main()

    assert output_file.exists()
    data = json.load(output_file.open(encoding="utf-8"))
    assert "foundation" in data
    assert "themes" in data
    assert set(data["themes"].keys()) == {"dark", "light", "pastel", "catppuccin"}
    # 스페이싱 값이 추출되어야 함 (v3 토큰 기준) / spacing values must be extracted (v3 tokens)
    # v3 design tokens: --elev-* are per-theme (not in :root); check spacing instead
    assert data["foundation"]["spacing"]  # spacing section must be non-empty

    # 🔴 키 존재만 보던 위 단언은 **테마 값이 전부 `{}` 여도 통과했다** — 실제로 그 상태로
    # 오래 green 이었다(themes.css 가 stub 이 되고 선택자가 `[data-theme=]` 로 바뀐 뒤).
    # 값 비어있음을 직접 막는다.
    # The keys-only assertion above passed while every theme was `{}`; assert content, not shape.
    assert all(data["themes"][name] for name in ("dark", "light", "pastel", "catppuccin")), (
        "테마 값이 비었다 — 선택자/소스 파일이 바뀌었는데 키만 남은 상태다 "
        f"(각 테마 크기: { {k: len(v) for k, v in data['themes'].items()} })"
    )


# ── 완전성 (실제 CSS 대상) / completeness against the real CSS ────────────
#
# 🔴 위 12개 단위 테스트는 **합성 fixture** 를 쓴다. fixture 는 구 CSS 구조
# (`body[data-theme="dark"]`, 단일 `:root`)를 인코딩하고 있어서, 실제 CSS 가 옮겨가도
# 절대 실패하지 않는다 — 즉 리팩터 drift 에 대해 구조적으로 무력하다.
# 실측 사고: 추출기가 174 선언 중 35 개만 산출하고 exit 0 했는데 이 스위트는 13/13 green.
# 스위트가 깨진 상태를 **인증**하고 있었다.
# The unit tests above use synthetic fixtures encoding the OLD CSS shape, so they cannot fail
# when the real CSS moves. The suite was certifying a broken extractor (35 of 174 emitted).


def _real_sources():
    """스크립트가 실제로 읽는 CSS 원문 / The CSS the script actually reads."""
    import extract_design_tokens as mod

    return [
        mod.TOKENS_CSS.read_text(encoding="utf-8"),
        mod.THEMES_CSS.read_text(encoding="utf-8"),
    ]


def test_every_declared_token_reaches_the_output():
    """🔴 S ⊆ E — 수집 대상 블록에 선언된 이름은 전부 출력에 실려야 한다.

    임의 하한(magic floor)이 아니라 **집합 포함 관계**라 CSS 가 늘거나 줄어도 썩지 않는다.
    이 단언이 없으면 다음 리팩터에서 또 조용히 열화한다 — 실제로 그렇게 됐었다.
    Set containment, not a floor: cannot rot as the CSS grows or shrinks.
    """
    import extract_design_tokens as mod

    sources = _real_sources()
    themes, variants = mod.collect_themes(sources)
    output = {
        "foundation": mod.categorize_root_vars(mod.collect_root(sources)),
        "themes": themes,
        "variants": variants,
    }
    missing = sorted(mod.declared_names(sources) - mod.emitted_names(output))
    assert not missing, f"선언됐으나 출력에 없는 토큰 {len(missing)}개: {missing[:15]}"


def test_root_collection_reads_every_root_block():
    """🔴 `:root` 가 여러 개다 — `re.search`(첫 블록만) 회귀 차단.

    구 버전이 정확히 이 실수를 했고, 두 번째 블록 31개 선언이 통째로 사라졌다.
    """
    import extract_design_tokens as mod

    css = "\n".join(_real_sources())
    block_count = len(mod._ROOT_BLOCK_RE.findall(mod._strip_comments(css)))
    assert block_count >= 2, (
        f":root 블록이 {block_count}개 — 이 가드의 전제(복수 블록)가 사라졌다. "
        "CSS 구조가 바뀐 것이니 수집 로직을 재검토할 것."
    )
    merged = mod.collect_root(_real_sources())
    first_only = mod.parse_vars(mod._ROOT_BLOCK_RE.findall(mod._strip_comments(css))[0])
    assert len(merged) > len(first_only), (
        "병합 결과가 첫 블록과 같다 — findall 이 search 로 회귀했을 가능성"
    )


def test_variant_blocks_are_not_folded_into_base_theme():
    """🔴 `[data-variant]` 는 **특이도가 더 높다** — base 에 합치면 기본값을 오염시킨다.

    `[data-theme="dark"]` = (0,1,0) vs `[data-theme="dark"][data-variant="signature"]` = (0,2,0).
    variant 는 그 속성이 있을 때만 적용되는데, 병합하면 항상 적용된 것처럼 보인다.
    Variant selectors have higher specificity; folding them in would present variant-only values
    as defaults.
    """
    import extract_design_tokens as mod

    themes, variants = mod.collect_themes(_real_sources())
    assert variants, "variant 블록이 하나도 수집되지 않았다 — 선택자 변경 의심"
    for theme, blocks in variants.items():
        for variant_name, block in blocks.items():
            assert block, f"{theme}/{variant_name} variant 블록이 비었다"

    # 🔴 핵심 단언 — base 맵이 **plain 블록만으로 만든 것과 정확히 같아야** 한다.
    #
    # 왜 이렇게까지 하나: 더 약한 단언들은 전부 무력했다(실측으로 확인).
    #   · "variant 전용 키 존재" → signature 는 새 키를 추가하지 않고 기존 키를 덮으므로 항상 실패
    #   · "겹치는 키 중 base≠variant 인 사례 존재" → 단 1개만 있어도 통과하는데, 이후 plain
    #     블록이 덮는 키가 항상 1개는 있어 **folding 이 일어나도 green**이었다
    # 실측 피해 규모: signature 18키 중 **17키는 이후 plain 블록이 덮지 않는다** → folding 시
    # 그 17개가 `data-variant` 없는 기본 화면 값으로 잘못 표기된다.
    #
    # 🔴 구현과 **독립된 방법**으로 기대값을 만든다 — 선택자 문자열 완전 일치로 블록을 고른다
    #   (구현은 정규식 + sub() 를 쓴다). 구현을 복사하면 구현의 버그까지 복사한다.
    # Build the expectation independently (exact selector-string match) rather than reusing the
    # implementation's regex, so a bug in the implementation cannot be copied into the oracle.
    expected: dict = {}
    for text in _real_sources():
        clean = mod._strip_comments(text)
        for match in re.finditer(r"([^{}]*)\{([^}]*)\}", clean, re.DOTALL):
            selector = match.group(1).strip().split("\n")[-1].strip()
            for name in ("dark", "light", "pastel", "catppuccin"):
                if selector == f'[data-theme="{name}"]':
                    expected.setdefault(name, {}).update(mod.parse_vars(match.group(2)))

    assert expected, "독립 파싱이 plain 테마 블록을 하나도 못 찾았다 — 오라클 전제 붕괴"
    for name, want in expected.items():
        assert themes[name] == want, (
            f"{name} base 맵이 plain 블록만의 결과와 다르다 — variant 가 흡수됐을 가능성. "
            f"불일치 키: {sorted(k for k in want if themes[name].get(k) != want[k])[:8]}"
        )


def test_uncategorized_tokens_are_kept_not_dropped():
    """🔴 prefix 어디에도 안 맞는 토큰은 `other` 로 보존한다 — 조용한 드롭 차단.

    구 버전은 `:root` 를 전부 읽어도 `--font-sans`·`--density`·`--lh-*` 등 14개를 버렸다.
    블록 커버리지만 보는 관측자는 이 손실을 통과시키므로 드롭 자체를 없앴다.
    """
    import extract_design_tokens as mod

    root_vars = mod.collect_root(_real_sources())
    categories = mod.categorize_root_vars(root_vars)
    kept = {k for cat in categories.values() for k in cat}
    assert set(root_vars) == kept, (
        f"카테고리 분류에서 토큰이 사라졌다: {sorted(set(root_vars) - kept)[:10]}"
    )
