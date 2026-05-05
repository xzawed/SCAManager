"""Phase 4 PR-14 회귀 가드 — Tier2 review_guides 20 언어 × 3 출력 언어 = 60 영역.

Phase 4 PR-14 regression guards — Tier2 review_guides 20 langs × 3 output langs = 60 areas.

검증 범위 (Coverage):
1. Tier2 20 언어 모든 가이드 — FULL/COMPACT × en/ko/ja 변형 보유 검증
2. output_language='en' (default) — 영문 반환
3. output_language='ko' / 'ja' → 해당 언어 반환
4. 각 가이드 헤더 일관성 (review checklist / 검토 기준 / レビュー基準)
"""
from __future__ import annotations

import pytest

from src.analyzer.pure.review_guides import get_guide

_TIER2 = [
    "php", "swift", "kotlin", "scala", "shell", "powershell",
    "sql", "dart", "lua", "perl", "r", "elixir", "haskell",
    "clojure", "groovy", "html", "css", "solidity", "objc", "fsharp",
]


# ── Tier2 20 언어 × 3 출력 언어 헤더 검증 ──────────────────────────────


@pytest.mark.parametrize("lang", _TIER2)
def test_tier2_full_english(lang):
    """Tier2 20 언어 — FULL 영문 반환 + `review checklist` 헤더 일관성."""
    guide = get_guide(lang, "full", output_language="en")
    assert isinstance(guide, str)
    assert len(guide) > 50
    assert "review checklist" in guide.lower()
    # 한국어 헤더 부재 확인 (영문 default)
    assert "검토 기준" not in guide


@pytest.mark.parametrize("lang", _TIER2)
def test_tier2_full_korean(lang):
    """Tier2 20 언어 — FULL 한국어 반환 + `검토 기준` 헤더 일관성."""
    guide = get_guide(lang, "full", output_language="ko")
    assert isinstance(guide, str)
    assert len(guide) > 50
    assert "검토 기준" in guide


@pytest.mark.parametrize("lang", _TIER2)
def test_tier2_full_japanese(lang):
    """Tier2 20 언어 — FULL 일본어 반환 + `レビュー基準` 헤더 일관성."""
    guide = get_guide(lang, "full", output_language="ja")
    assert isinstance(guide, str)
    assert len(guide) > 50
    assert "レビュー基準" in guide


# ── COMPACT 3 언어 distinct ─────────────────────────────────────────────


@pytest.mark.parametrize("lang", _TIER2)
def test_tier2_compact_3_languages_distinct(lang):
    """Tier2 20 언어 — COMPACT 3 언어 모두 다른 텍스트 (cache key 분기 검증)."""
    en = get_guide(lang, "compact", output_language="en")
    ko = get_guide(lang, "compact", output_language="ko")
    ja = get_guide(lang, "compact", output_language="ja")
    assert en != ko
    assert en != ja
    assert ko != ja


# ── Tier2 fallback to English when invalid output_language ─────────────


def test_tier2_invalid_output_language_falls_to_english():
    """invalid output_language → 영문 fallback."""
    en = get_guide("php", "full", output_language="en")
    invalid = get_guide("php", "full", output_language="zh")
    assert en == invalid


def test_tier2_default_output_language_is_english():
    """get_guide — output_language default = 'en' (Tier2)."""
    en_explicit = get_guide("php", "full", output_language="en")
    en_default = get_guide("php", "full")
    assert en_explicit == en_default
