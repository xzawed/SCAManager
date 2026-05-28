"""
토큰 추출 스크립트 단위 테스트.
Unit tests for the design token extraction script.
"""
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
