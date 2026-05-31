"""settings.* i18n 키 존재 테스트 — 사이클 146 Sprint 3.

settings.* i18n key existence tests — Cycle 146 Sprint 3.
"""
from __future__ import annotations

import json
import pathlib

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
_KEYS = [
    "model_card_title", "badge_advanced", "use_global_default",
    "preset_minimal", "preset_standard", "preset_strict",
    "field_pr_review_comment", "field_commit_comment", "field_create_issue",
    "field_railway_deploy_alerts", "field_approve_mode", "field_auto_merge",
    "field_approve_threshold", "field_reject_threshold", "field_merge_threshold",
    "mode_auto", "mode_semi_auto",
    "preset_applied_suffix", "hide_value", "show_value",
]


def _load(locale):
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_settings_key_exists(locale, key):
    assert key in _load(locale)["settings"], f"[{locale}] settings.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_settings_non_empty(locale, key):
    val = _load(locale)["settings"].get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] {key} 비어있음"
