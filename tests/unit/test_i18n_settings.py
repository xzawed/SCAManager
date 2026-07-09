"""settings.* i18n 키 존재 테스트 — 사이클 146 Sprint 3.

settings.* i18n key existence tests — Cycle 146 Sprint 3.

🔴 _KEYS ↔ 템플릿 양방향 가드 (2026-07-09 회고 후속 ②): _KEYS 는 손으로 유지되는 목록이라
settings.html 참조와 자연 drift 한다. #1041 에서 키 제거 시 _KEYS 에 잔존 → CI 6-fail 사고.
아래 test_keys_match_template 이 _KEYS 집합 == settings.html 의 settings.* 참조 집합을 강제해
양방향 drift (템플릿 추가/_KEYS 누락 = silent 커버리지 갭, _KEYS 잔존/템플릿 제거 = dead 참조)
를 모두 가시화한다.
🔴 _KEYS ↔ template bidirectional guard: _KEYS is hand-maintained, so it drifts from the
settings.html references. test_keys_match_template enforces set-equality to surface drift both ways.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_SETTINGS_TMPL = pathlib.Path("src/templates/settings.html")
_LOCALES = ["ko", "en", "ja"]
_KEYS = [
    "model_card_title", "use_global_default",
    "preset_minimal", "preset_standard", "preset_strict",
    "field_pr_review_comment", "field_commit_comment", "field_create_issue",
    "field_railway_deploy_alerts", "field_approve_mode", "field_auto_merge",
    "field_approve_threshold", "field_reject_threshold", "field_merge_threshold",
    "mode_auto", "mode_semi_auto",
    "preset_applied_suffix", "hide_value", "show_value",
    "save_toast_ok", "save_toast_err", "model_hint",
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


def _template_settings_refs() -> set[str]:
    # settings.html 의 모든 settings.<key> i18n 참조 추출.
    # Extract every settings.<key> i18n reference from settings.html.
    return set(re.findall(r"settings\.([a-z_]+)", _SETTINGS_TMPL.read_text(encoding="utf-8")))


def test_keys_match_template():
    """_KEYS 집합 == settings.html 의 settings.* 참조 집합 (양방향 drift 가드).

    _KEYS set must equal the settings.* references in settings.html (bidirectional drift guard).
    - 템플릿에만 있는 키 = _KEYS 누락 (silent 커버리지 갭) → 존재/비어있음 테스트 미적용.
    - _KEYS 에만 있는 키 = 템플릿 제거 후 잔존 (dead 참조) → #1041 6-fail 사고 유형.
    신규 settings.* 키를 JS/base.html 전용으로 도입해 예외가 필요하면, 여기에 명시적 예외 집합을
    추가하고 사유를 주석으로 남긴다 (침묵 drift 금지).
    """
    tmpl_keys = _template_settings_refs()
    keys = set(_KEYS)
    assert keys == tmpl_keys, (
        f"_KEYS ↔ settings.html drift — 템플릿에만(={sorted(tmpl_keys - keys)}) / "
        f"_KEYS에만(={sorted(keys - tmpl_keys)}). "
        "키 추가/제거 시 _KEYS 와 settings.html 을 동시 갱신하라 (#1041 학습)."
    )


def test_keys_no_duplicates():
    """_KEYS 에 중복 없음 (손유지 목록 오타 방어).

    _KEYS has no duplicates (guards against hand-maintained-list typos).
    """
    assert len(_KEYS) == len(set(_KEYS)), f"_KEYS 중복: {[k for k in set(_KEYS) if _KEYS.count(k) > 1]}"
