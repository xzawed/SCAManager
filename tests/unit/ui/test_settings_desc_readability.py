"""설정 페이지 옵션 설명(description) 가독성 개선 정적 가드.

Static guards for settings-page option-description readability:
`--text-desc` 중간 대비 CSS 변수(color-mix) 도입 + `.t-desc` 크기/색상 갱신,
그리고 6개 desc i18n 키의 하드코딩 `<br>` 제거(자연 줄바꿈) + render-parity.
Introduces a medium-contrast `--text-desc` CSS variable (color-mix) and updates
`.t-desc` size/color, plus removal of hardcoded `<br>` from 6 desc i18n keys
(natural text wrap) + render-parity across locales.

배경 (Background):
    설정 페이지의 옵션 설명이 너무 작고(11px) 대비가 낮으며(--text-2 그대로)
    일부는 `<br>` 로 줄바꿈이 강제되어 장문처럼 보였다. Part 1(타이포그래피) +
    Part 2(카피 간결화)로 가독성을 개선한다.
    Settings-page option descriptions were too small (11px), low-contrast
    (bare --text-2), and some were forced to wrap via hardcoded `<br>`, reading
    as verbose. Part 1 (typography) + Part 2 (concise copy) improve readability.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.i18n.loader import get_text

_SETTINGS = Path("src/templates/settings.html")
_LOCALES = ("ko", "en", "ja")


def _read() -> str:
    return _SETTINGS.read_text(encoding="utf-8")


# ── Part 1: 타이포그래피 (CSS) ───────────────────────────────────────────


def test_text_desc_variable_defined_via_color_mix():
    """`--text-desc` 변수가 `color-mix(in srgb, ...)` 로 정의됨 (theme-adaptive medium contrast).

    `--text-desc` is defined via `color-mix(in srgb, ...)` (theme-adaptive medium
    contrast) — no new raw hex token.
    """
    html = _read()
    match = re.search(r"--text-desc:\s*color-mix\(in srgb,[^;]+\);", html)
    assert match, "--text-desc 변수가 color-mix 로 정의되지 않음"
    # var(--text-1) 과 var(--text-2) 를 혼합해야 medium contrast 의도를 만족.
    # Must mix var(--text-1) and var(--text-2) to satisfy the medium-contrast intent.
    assert "var(--text-1)" in match.group(0)
    assert "var(--text-2)" in match.group(0)


def test_toggle_info_t_desc_uses_12px_and_text_desc_token():
    """`.toggle-info .t-desc` 규칙이 `12px` + `var(--text-desc)` 를 사용 (구 11px/--text-2 아님).

    The `.toggle-info .t-desc` rule uses `12px` + `var(--text-desc)`
    (not the old 11px / bare --text-2).
    """
    html = _read()
    match = re.search(r"\.toggle-info \.t-desc\s*\{([^}]+)\}", html)
    assert match, ".toggle-info .t-desc 규칙을 찾을 수 없음"
    rule = match.group(1)
    assert "12px" in rule, f".t-desc 가 12px 를 사용하지 않음: {rule!r}"
    assert "11px" not in rule, f".t-desc 에 구 11px 잔존: {rule!r}"
    assert "var(--text-desc)" in rule, f".t-desc 가 var(--text-desc) 를 사용하지 않음: {rule!r}"
    assert "var(--text-2)" not in rule, f".t-desc 에 구 bare var(--text-2) 잔존: {rule!r}"


def test_field_hint_uses_12px_and_text_desc_token():
    """`.field-hint` 규칙이 `12px` + `var(--text-desc)` + `line-height` 를 사용."""
    # `.field-hint` rule uses 12px + var(--text-desc) + line-height.
    html = _read()
    match = re.search(r"\.field-hint\s*\{([^}]+)\}", html)
    assert match, ".field-hint 규칙을 찾을 수 없음"
    rule = match.group(1)
    assert "12px" in rule
    assert "var(--text-desc)" in rule
    assert "line-height" in rule


def test_preset_hint_and_preset_desc_use_text_desc_token():
    """`.preset-hint` / `.preset-desc` 규칙 모두 `var(--text-desc)` 사용 (medium contrast 일관성)."""
    # Both `.preset-hint` and `.preset-desc` use var(--text-desc) for consistent medium contrast.
    html = _read()
    hint_match = re.search(r"\.preset-hint\s*\{([^}]+)\}", html)
    desc_match = re.search(r"\.preset-desc\s*\{([^}]+)\}", html)
    assert hint_match, ".preset-hint 규칙을 찾을 수 없음"
    assert desc_match, ".preset-desc 규칙을 찾을 수 없음"
    assert "var(--text-desc)" in hint_match.group(1)
    assert "12px" in hint_match.group(1)
    assert "var(--text-desc)" in desc_match.group(1)


# ── Part 2: 카피 간결화 (i18n) ───────────────────────────────────────────

# `<br>` 로 강제 줄바꿈되던 6개 desc 키 — 자연 줄바꿈(wrap)으로 전환 대상.
# The 6 desc keys previously forced to wrap via `<br>` — now wrap naturally.
_BR_REMOVED_KEYS = [
    "settings_page.pr_rules.auto_merge_desc",
    "settings_page.pr_rules.merge_issue_desc",
    "settings_page.post_event.commit_comment_desc",
    "settings_page.post_event.create_issue_desc",
    "settings_page.post_event.railway_alerts_desc",
    "settings_page.danger.delete_repo_desc",
]

# 이번 작업으로 카피가 갱신된 전체 키(위 6개 + ai_review_desc + model_hint) —
# 존재/비어있지 않음 render-parity 대상.
# All keys touched by this change (the 6 above + ai_review_desc + model_hint) —
# subject to existence/non-empty render-parity checks.
_CHANGED_KEYS = _BR_REMOVED_KEYS + [
    "settings_page.pr_rules.ai_review_desc",
    "settings.model_hint",
]


@pytest.mark.parametrize("key", _BR_REMOVED_KEYS)
@pytest.mark.parametrize("locale", _LOCALES)
def test_br_removed_from_desc_key(key: str, locale: str):
    """`<br>` 하드코딩 줄바꿈이 제거되어 자연 wrap 으로 전환됨 (3 로케일 공통)."""
    # Hardcoded `<br>` line breaks are removed in favor of natural wrap (all 3 locales).
    value = get_text(key, locale)
    assert "<br>" not in value, f"[{locale}] {key} 에 <br> 잔존: {value!r}"


@pytest.mark.parametrize("key", _CHANGED_KEYS)
@pytest.mark.parametrize("locale", _LOCALES)
def test_changed_key_exists_and_non_empty(key: str, locale: str):
    """변경 대상 키가 3 로케일 모두 존재 + 비어있지 않음 (raw 키 미노출 = render-parity)."""
    # The changed key exists and is non-empty in all 3 locales (no raw-key leak = render-parity).
    value = get_text(key, locale)
    assert value and value != key, f"[{locale}] {key} 미존재 또는 raw 키 노출: {value!r}"
