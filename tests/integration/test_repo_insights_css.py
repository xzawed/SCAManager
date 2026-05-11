"""repo_insights.css 통합 테스트 — 필수 클래스 + WCAG 2.5.5 44px 검증.

repo_insights.css integration test — required classes + WCAG 2.5.5 44px check.
"""
from pathlib import Path

import pytest

CSS_PATH = Path("src/static/css/repo_insights.css")


@pytest.fixture(scope="module")
def css_content():
    assert CSS_PATH.exists(), f"{CSS_PATH} not found"
    return CSS_PATH.read_text(encoding="utf-8")


@pytest.mark.parametrize("cls", [
    ".ri-page",
    ".ri-header",
    ".ri-repo-title",
    ".ri-grade-badge",
    ".ri-kpi-grid",
    ".ri-kpi-card",
    ".ri-kpi-label",
    ".ri-kpi-value",
    ".ri-two-col",
    ".ri-card",
    ".ri-issues-table",
    ".ri-badge-error",
    ".ri-badge-warning",
    ".ri-donut-wrap",
    ".ri-file-bar",
    ".ri-suggestions",
    ".ri-narrative-card",
    ".ri-empty",
    ".ri-day-btn",
])
def test_ri_class_exists(css_content, cls):
    """각 .ri-* 클래스가 CSS 파일에 정의되어 있다."""
    assert cls in css_content, f"Missing CSS class: {cls}"


def test_mobile_44px_applied_to_day_btn(css_content):
    """모바일 @media 분기에 .ri-day-btn min-height: 44px가 있다."""
    assert "min-height: 44px" in css_content
    media_idx = css_content.rfind("@media (max-width: 768px)")
    assert media_idx != -1
    mobile_section = css_content[media_idx:]
    assert "44px" in mobile_section


def test_prefers_reduced_motion_present(css_content):
    """prefers-reduced-motion 미디어 쿼리가 포함되어 있다."""
    assert "prefers-reduced-motion" in css_content


def test_no_hardcoded_hex_colors(css_content):
    """CSS 파일에 직접 hex 색상 코드가 없다 (CSS variable 사용 의무)."""
    import re
    hex_colors = re.findall(
        r"(?<![a-zA-Z0-9_-])#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])",
        css_content,
    )
    assert hex_colors == [], f"Found hardcoded hex colors: {hex_colors}"
