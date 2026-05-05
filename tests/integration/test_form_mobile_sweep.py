"""add_repo / login 모바일 form sweep 회귀 가드 (Cycle 81 PR-D — 영역 🅑 종결).

5+1 cross-verify (관점 🅑) PR-D 의무:
- add_repo.html 모바일 768px↓ + 480px↓ 분기 신설
- login.html 모바일 768px↓ 분기 강화 (기존 480px↓ 보존)
- WCAG 2.5.5 ≥44px (form-select / back-btn) + ≥48px (btn-primary / btn-github)
- iOS Safari focus zoom 회피 (form-select font-size 16px — 이미 적용 보존 검증)

Cycle 81 PR-A fix-up 학습 — HTML 정적 검증 (CSS string in) — 운영 endpoint 무관.
"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def add_repo_html() -> str:
    return (Path(__file__).resolve().parents[2] / "src" / "templates" / "add_repo.html").read_text()


@pytest.fixture(scope="module")
def login_html() -> str:
    return (Path(__file__).resolve().parents[2] / "src" / "templates" / "login.html").read_text()


# ─── add_repo.html 모바일 분기 신설 ──────────────────────────────


def test_add_repo_mobile_768px_branch_exists(add_repo_html):
    """add_repo.html 모바일 768px↓ 분기 신설 (Cycle 81 PR-D)."""
    assert "@media (max-width: 768px)" in add_repo_html


def test_add_repo_mobile_480px_branch_exists(add_repo_html):
    """add_repo.html 모바일 480px↓ 분기 신설 (PR-D 신규)."""
    assert "@media (max-width: 480px)" in add_repo_html


def test_add_repo_form_select_wcag_44px(add_repo_html):
    """`.form-select` 모바일 ≥44px (WCAG 2.5.5)."""
    idx = add_repo_html.find("@media (max-width: 768px)")
    block = add_repo_html[idx:idx + 800]
    assert ".form-select { min-height: 44px;" in block


def test_add_repo_btn_primary_wcag_48px(add_repo_html):
    """`.btn-primary` 모바일 ≥48px (의무 액션)."""
    idx = add_repo_html.find("@media (max-width: 768px)")
    block = add_repo_html[idx:idx + 800]
    assert ".btn-primary { min-height: 48px; }" in block


def test_add_repo_back_btn_wcag_44px(add_repo_html):
    """`.back-btn` 모바일 ≥44px."""
    idx = add_repo_html.find("@media (max-width: 768px)")
    block = add_repo_html[idx:idx + 800]
    assert ".back-btn { min-height: 44px;" in block


def test_add_repo_form_select_ios_focus_zoom_preserved(add_repo_html):
    """`.form-select` font-size 16px (iOS focus zoom 회피) 보존 검증."""
    # 기존 line 43 = font-size 16px (PR-D 변경 무관)
    assert "font-size: 16px;" in add_repo_html


# ─── login.html 모바일 분기 강화 ────────────────────────────────


def test_login_mobile_768px_branch_exists(login_html):
    """login.html 모바일 768px↓ 분기 신설 (PR-D)."""
    assert "@media (max-width: 768px)" in login_html


def test_login_btn_github_wcag_48px(login_html):
    """`.btn-github` 모바일 ≥48px (OAuth 의무 액션 — WCAG 권장)."""
    idx = login_html.find("@media (max-width: 768px)")
    block = login_html[idx:idx + 500]
    assert ".btn-github { min-height: 48px; }" in block


def test_login_existing_480px_branch_preserved(login_html):
    """기존 login 480px↓ 분기 보존 (회귀 0)."""
    assert "@media (max-width: 480px)" in login_html
    # 기존 분기 영역 = .login-wrap + .login-card padding
    idx = login_html.find("@media (max-width: 480px)")
    block = login_html[idx:idx + 300]
    assert ".login-wrap" in block
    assert ".login-card" in block


# ─── 회귀 가드 (PR-A/B/C 영역 무영향) ──────────────────────────


def test_pwa_manifest_unchanged():
    """PR-A PWA manifest = 본 PR 무영향."""
    manifest = (Path(__file__).resolve().parents[2] / "src" / "static" / "manifest.json").read_text()
    assert '"display": "standalone"' in manifest


def test_dashboard_mobile_priority_unchanged():
    """PR-B dashboard 모바일 KPI 우선순위 = 본 PR 무영향."""
    dashboard_html = (Path(__file__).resolve().parents[2] / "src" / "templates" / "dashboard.html").read_text()
    assert ".dash-kpi:nth-child(3) { order: 1;" in dashboard_html


def test_settings_mobile_768px_unchanged():
    """PR-C settings 모바일 768px↓ = 본 PR 무영향."""
    settings_html = (Path(__file__).resolve().parents[2] / "src" / "templates" / "settings.html").read_text()
    assert "@media (max-width: 768px)" in settings_html
    assert ".s-card-body { padding: 0.85rem; }" in settings_html
