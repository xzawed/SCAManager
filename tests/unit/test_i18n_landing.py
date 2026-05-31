"""landing.* i18n 키 존재 테스트 — 사이클 146 Sprint 4.

landing.* i18n key existence tests — cycle 146 Sprint 4.
"""
from __future__ import annotations

import json
import pathlib

import pytest

_TRANS_DIR = pathlib.Path("src/i18n/translations")
_LOCALES = ["ko", "en", "ja"]
# landing.html 실제 구현 키 — 템플릿 교체 항목과 1:1 일치
# landing.html actual keys — 1:1 match with template replacements
_KEYS = [
    "page_title",
    "error_oauth_failed",
    "error_generic",
    "close_aria",
    "badge",
    "hero_title_1",
    "hero_gradient",
    "hero_sub",
    "cta_start",
    "cta_github",
    "grade_preview_aria",
    "demo_review_1",
    "demo_review_2",
    "demo_review_3",
    "demo_review_4",
    "stat_languages",
    "stat_tools_value",
    "stat_tools",
    "stat_channels_value",
    "stat_channels",
    "stat_ai",
    "features_heading",
    "feature_auto_title",
    "feature_auto_desc",
    "feature_gate_title",
    "feature_gate_desc",
    "feature_score_title",
    "feature_score_desc",
    "feature_notify_title",
    "feature_notify_desc",
    "grade_section_label",
    "grade_a_aria",
    "grade_b_aria",
    "grade_c_aria",
    "grade_d_aria",
    "grade_f_aria",
]


def _load(locale: str) -> dict:
    return json.loads((_TRANS_DIR / f"{locale}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_landing_key_exists(locale: str, key: str) -> None:
    """landing 네임스페이스 + 키 존재 검증.

    Validate landing namespace + key existence.
    """
    data = _load(locale)
    assert "landing" in data, f"[{locale}] landing 네임스페이스 없음"
    assert key in data["landing"], f"[{locale}] landing.{key} 없음"


@pytest.mark.parametrize("locale", _LOCALES)
@pytest.mark.parametrize("key", _KEYS)
def test_landing_non_empty(locale: str, key: str) -> None:
    """landing 키 값이 비어있지 않은 문자열인지 검증.

    Validate landing key value is a non-empty string.
    """
    val = _load(locale)["landing"].get(key)
    assert isinstance(val, str) and val.strip(), f"[{locale}] {key} 비어있음"


def test_landing_demo_review_html_preserved() -> None:
    """데모 리뷰 키에 <strong> HTML 구조 보존 검증 (3 언어).

    Validate <strong> HTML structure preserved in demo review keys (3 locales).
    """
    for locale in _LOCALES:
        landing = _load(locale)["landing"]
        for key in ["demo_review_1", "demo_review_2", "demo_review_3", "demo_review_4"]:
            assert "<strong>" in landing[key] and "</strong>" in landing[key], (
                f"[{locale}] {key} <strong> 태그 누락"
            )
