"""common.theme.* i18n 키 존재 테스트 — 사이클 146 Sprint 1.

Tests that common.theme.* keys exist in all 3 locales.
"""
from __future__ import annotations
import json
import pathlib
import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_THEME_KEYS = [
    "dark_label", "light_label", "pastel_label", "catppuccin_label",
    "dark_short", "light_short", "pastel_short", "catppuccin_short",
]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _THEME_KEYS)
def test_common_theme_key_exists(locale: str, key: str):
    """common.theme.<key>가 모든 locale에 존재해야 한다."""
    data = _load(locale)
    assert "theme" in data["common"], f"[{locale}] common.theme 없음"
    assert key in data["common"]["theme"], f"[{locale}] common.theme.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _THEME_KEYS)
def test_common_theme_value_non_empty(locale: str, key: str):
    """common.theme.<key> 값이 비어있지 않아야 한다."""
    val = _load(locale).get("common", {}).get("theme", {}).get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] common.theme.{key} 비어있음"
