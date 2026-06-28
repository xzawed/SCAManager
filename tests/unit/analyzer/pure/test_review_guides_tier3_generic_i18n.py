"""Phase 4 PR-15 회귀 가드 — Tier3 20 가이드 + generic 다국어.

Phase 4 PR-15 regression guards — Tier3 20 guides + generic i18n.

검증 범위 (Coverage):
1. Tier3 20 언어 모든 가이드 — FULL/COMPACT × en/ko/ja 변형 보유 검증
2. generic.py — FULL/COMPACT × en/ko/ja 변형 검증
3. output_language='en' (default) — 영문 반환
4. output_language='ko' / 'ja' → 해당 언어 반환
5. 각 가이드 헤더 일관성 (review checklist / 검토 기준 / レビュー基準)
6. unknown language → generic fallback (3 언어)
"""
from __future__ import annotations

import pytest

from src.analyzer.pure.review_guides import get_guide

_TIER3 = [
    "erlang", "ocaml", "julia", "zig", "nim", "crystal", "gleam",
    "elm", "vimscript", "gdscript", "dockerfile", "makefile",
    "terraform", "yaml", "toml", "graphql", "protobuf", "xml",
    "latex",
]


# ── Tier3 19 언어 × 3 출력 언어 헤더 검증 ──────────────────────────────


@pytest.mark.parametrize("lang", _TIER3)
def test_tier3_full_english(lang):
    """Tier3 20 언어 — FULL 영문 반환 + `review checklist` 헤더."""
    guide = get_guide(lang, "full", output_language="en")
    assert isinstance(guide, str)
    assert len(guide) > 50
    assert "review checklist" in guide.lower()
    # 한국어 헤더 부재 확인 (영문 default)
    assert "검토 기준" not in guide


@pytest.mark.parametrize("lang", _TIER3)
def test_tier3_full_korean(lang):
    """Tier3 20 언어 — FULL 한국어 반환 + `검토 기준` 헤더."""
    guide = get_guide(lang, "full", output_language="ko")
    assert isinstance(guide, str)
    assert len(guide) > 50
    assert "검토 기준" in guide


@pytest.mark.parametrize("lang", _TIER3)
def test_tier3_full_japanese(lang):
    """Tier3 20 언어 — FULL 일본어 반환 + `レビュー基準` 헤더."""
    guide = get_guide(lang, "full", output_language="ja")
    assert isinstance(guide, str)
    assert len(guide) > 50
    assert "レビュー基準" in guide


# ── COMPACT 3 언어 distinct ─────────────────────────────────────────────


@pytest.mark.parametrize("lang", _TIER3)
def test_tier3_compact_3_languages_distinct(lang):
    """Tier3 20 언어 — COMPACT 3 언어 모두 다른 텍스트 (cache key 분기 검증)."""
    en = get_guide(lang, "compact", output_language="en")
    ko = get_guide(lang, "compact", output_language="ko")
    ja = get_guide(lang, "compact", output_language="ja")
    assert en != ko
    assert en != ja
    assert ko != ja


# ── generic.py i18n ──────────────────────────────────────────────────────


def test_generic_full_3_languages_distinct():
    """generic.py — FULL 3 언어 distinct."""
    en = get_guide("unknown_xyz", "full", output_language="en")
    ko = get_guide("unknown_xyz", "full", output_language="ko")
    ja = get_guide("unknown_xyz", "full", output_language="ja")
    assert "Generic code review checklist" in en
    assert "일반 코드 검토 기준" in ko
    assert "一般コードレビュー基準" in ja
    assert en != ko != ja != en


def test_generic_compact_3_languages_distinct():
    """generic.py — COMPACT 3 언어 distinct."""
    en = get_guide("unknown_xyz", "compact", output_language="en")
    ko = get_guide("unknown_xyz", "compact", output_language="ko")
    ja = get_guide("unknown_xyz", "compact", output_language="ja")
    assert en != ko
    assert en != ja
    assert ko != ja


# ── Tier3 fallback ──────────────────────────────────────────────────────


def test_tier3_invalid_output_language_falls_to_english():
    """invalid output_language → 영문 fallback."""
    en = get_guide("erlang", "full", output_language="en")
    invalid = get_guide("erlang", "full", output_language="zh")
    assert en == invalid


def test_tier3_default_output_language_is_english():
    """get_guide — output_language default = 'en' (Tier3)."""
    en_explicit = get_guide("erlang", "full", output_language="en")
    en_default = get_guide("erlang", "full")
    assert en_explicit == en_default
