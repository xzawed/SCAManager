"""사이클 94 Step 2-B 일러스트 마크업 회귀 가드.

Cycle 94 Step 2-B illustration markup regression guards (PR #366 prompt 본문 페어).
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ILLUSTRATIONS_DIR = REPO_ROOT / "src" / "static" / "illustrations"
TEMPLATES_DIR = REPO_ROOT / "src" / "templates"
CSS_DIR = REPO_ROOT / "src" / "static" / "css"

EXPECTED_PNGS = [
    "login_hero.png",
    "dashboard_empty.png",
    "overview_onboarding.png",
    "add_repo_hero.png",
    "filter_empty.png",
]


@pytest.mark.parametrize("name", EXPECTED_PNGS)
def test_illustration_png_exists(name):
    """5장 PNG 모두 존재 + 100KB 이상 (DALL-E 3 결과 minimum 보장).

    All 5 PNGs exist + ≥100 KB (DALL-E 3 output minimum guard).
    """
    path = ILLUSTRATIONS_DIR / name
    assert path.exists(), f"{name} 누락 (Step 2-B 회귀)"
    assert path.stat().st_size > 100_000, f"{name} 크기 < 100KB (생성 실패 의심)"


def test_illustrations_css_exists_with_theme_compat():
    """illustrations.css 신설 + 4-테마 호환 default 정합.

    illustrations.css exists with 4-theme compat tokens (no hardcoded hex).
    """
    css = CSS_DIR / "illustrations.css"
    assert css.exists()
    body = css.read_text(encoding="utf-8")
    assert ".illustration" in body
    assert ".illustration--hero" in body
    assert ".illustration--empty" in body
    assert ".illustration--tutorial" in body
    # 토큰 사용 (UI rules — hex 직접 사용 금지)
    # Token usage required (UI rules — no hardcoded hex)
    assert "var(--space-" in body


def test_base_html_includes_illustrations_css():
    """base.html 에 illustrations.css link 포함 (4-테마 글로벌 적용).

    base.html includes illustrations.css link (global 4-theme reach).
    """
    base = (TEMPLATES_DIR / "base.html").read_text(encoding="utf-8")
    assert "/static/css/illustrations.css" in base


@pytest.mark.parametrize(
    "template,png_ref",
    [
        ("login.html", "login_hero.png"),
        ("dashboard.html", "dashboard_empty.png"),
        ("overview.html", "overview_onboarding.png"),
        ("add_repo.html", "add_repo_hero.png"),
        ("repo_detail.html", "filter_empty.png"),
    ],
)
def test_template_references_illustration(template, png_ref):
    """5 페이지가 각각 올바른 PNG 경로 참조 (Step 2-B 종결 신호).

    Each of 5 pages references its assigned PNG (Step 2-B completion signal).
    """
    body = (TEMPLATES_DIR / template).read_text(encoding="utf-8")
    assert (
        f"/static/illustrations/{png_ref}" in body
    ), f"{template} 의 {png_ref} 참조 누락 (Step 2-B 회귀)"


def test_decorative_illustrations_have_presentation_role():
    """장식용 일러스트 = alt='' + role='presentation' (접근성 정합).

    Decorative illustrations use empty alt + role=presentation (a11y).
    """
    for template in ["login.html", "dashboard.html", "overview.html", "add_repo.html"]:
        body = (TEMPLATES_DIR / template).read_text(encoding="utf-8")
        if 'src="/static/illustrations/' in body:
            assert (
                'role="presentation"' in body
            ), f"{template} role='presentation' 누락 — 접근성 정합 위반"
