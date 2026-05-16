"""settings 모바일 768px↓ 분기 회귀 가드 (Cycle 81 PR-C — 영역 🅑 모바일).

5+1 cross-verify (관점 🅑) PR-C 의무:
- 768px↓ 분기 신설 (mobile portrait 호환)
- 카드 padding 축소 (`.s-card-body` 1.1rem → 0.85rem)
- 카드 헤더 폰트 축소 (`.s-card-hdr .hdr-title` 13px → 12.5px)
- WCAG 2.5.5 ≥44px 가드 (button + select + input)
- iOS Safari focus zoom 회피 (font-size ≥16px)

Progressive Disclosure (`<details>` wrap) 는 Phase 2 영역 보류 (5-way sync 영향 위험).

Cycle 81 PR-A fix-up 학습 (TestClient lifespan 비활성):
- HTML 정적 검증 (CSS string in) — 운영 endpoint 무관
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def settings_html() -> str:
    """settings.html 본문 read (templates 정적 자원)."""
    return (Path(__file__).resolve().parents[2] / "src" / "templates" / "settings.html").read_text(encoding='utf-8')


# ─── 768px↓ 분기 신설 ────────────────────────────────────────────


def test_settings_mobile_768px_branch_exists(settings_html):
    """모바일 768px↓ 분기 신설 (Cycle 81 PR-C 신규)."""
    assert "@media (max-width: 768px)" in settings_html


def test_settings_card_body_padding_shrink(settings_html):
    """카드 padding 축소 — 모바일 가독성 + 스크롤 부담 ↓."""
    # 모바일 분기 안 .s-card-body padding 축소 검증
    # Find the 768px branch and verify card body padding shrink
    idx = settings_html.find("@media (max-width: 768px)")
    assert idx > 0
    # 768px↓ 분기 안 (다음 800자 이내) 카드 padding 축소
    block = settings_html[idx:idx + 1500]
    assert ".s-card-body { padding: 0.85rem; }" in block
    assert ".s-card-hdr { padding: 0.6rem 0.85rem; }" in block


def test_settings_card_header_font_shrink(settings_html):
    """카드 헤더 폰트 축소 (모바일)."""
    idx = settings_html.find("@media (max-width: 768px)")
    block = settings_html[idx:idx + 1500]
    assert ".s-card-hdr .hdr-title { font-size: 12.5px; }" in block


# ─── WCAG 2.5.5 ≥44px 가드 ────────────────────────────────────────


def test_settings_mobile_wcag_gate_mode_btn(settings_html):
    """`.gate-mode-btn` 모바일 ≥44px (WCAG 2.5.5)."""
    idx = settings_html.find("@media (max-width: 768px)")
    block = settings_html[idx:idx + 1500]
    assert ".gate-mode-btn { min-height: 44px; }" in block


def test_settings_mobile_wcag_input_select(settings_html):
    """select + input 모바일 ≥44px + ≥16px (iOS Safari focus zoom 회피)."""
    idx = settings_html.find("@media (max-width: 768px)")
    block = settings_html[idx:idx + 1500]
    assert "select, input[type=text]" in block
    assert "min-height: 44px;" in block
    assert "font-size: 16px;" in block


def test_settings_mobile_wcag_save_btn(settings_html):
    """저장 버튼 모바일 ≥48px (의무 액션 — WCAG ≥48px 권장)."""
    idx = settings_html.find("@media (max-width: 768px)")
    block = settings_html[idx:idx + 1500]
    assert ".save-btn, button[type=submit] { min-height: 48px; }" in block


def test_settings_mobile_danger_summary_wrap(settings_html):
    """위험 구역 summary 모바일 ≥44px 가드."""
    idx = settings_html.find("@media (max-width: 768px)")
    block = settings_html[idx:idx + 1500]
    assert ".danger-summary-wrap summary" in block


# ─── 기존 480px↓ 분기 회귀 0 ──────────────────────────────────────


def test_existing_480px_branches_preserved(settings_html):
    """기존 480px↓ 분기 4 위치 모두 보존 (회귀 0)."""
    count = settings_html.count("@media (max-width: 480px)")
    assert count == 4, f"480px↓ 분기 4 위치 보존 의무 — 실측: {count}"


# ─── Progressive Disclosure 보류 검증 (Phase 2) ──────────────────


def test_existing_details_preserved(settings_html):
    """기존 `<details>` 영역 (preset 3 + 위험 구역) 보존 — Phase 2 추가 wrap X."""
    # preset 3건 = preset-minimal / preset-standard / preset-strict
    assert "preset-minimal" in settings_html
    assert "preset-standard" in settings_html
    assert "preset-strict" in settings_html
    # 위험 구역 = danger-summary-wrap
    assert "danger-summary-wrap" in settings_html


# ─── 회귀 가드 (PR-A + PR-B 영역 무영향) ──────────────────────


def test_pwa_manifest_unchanged():
    """PR-A PWA manifest = settings 변경 무영향."""
    manifest = (Path(__file__).resolve().parents[2] / "src" / "static" / "manifest.json").read_text(encoding='utf-8')
    assert '"display": "standalone"' in manifest
