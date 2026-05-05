"""Phase 4 PR-13 회귀 가드 — Tier1 review_guides 10 언어 × 3 언어 = 30 영역.

Phase 4 PR-13 regression guards — Tier1 review_guides 10 langs × 3 output langs = 30 areas.

검증 범위 (Coverage):
1. get_guide(language, mode, output_language) — 3 언어 모두 작동 (en/ko/ja)
2. Tier1 10 언어 모든 가이드 — FULL/COMPACT × ko/ja 변형 보유 검증
3. output_language='en' (default) — 기존 영문 (FULL/COMPACT) 반환
4. output_language='ko' / 'ja' → 해당 언어 반환 + 부재 시 영문 fallback
5. invalid output_language → 영문 fallback
6. build_review_prompt + build_review_blocks — language 인자 → output_language 전달 검증
"""
from __future__ import annotations

import pytest

from src.analyzer.pure.review_guides import get_guide, supported_languages
from src.analyzer.pure.review_prompt import build_review_blocks, build_review_prompt


_TIER1 = ["python", "javascript", "typescript", "java", "go",
          "rust", "c", "cpp", "csharp", "ruby"]


# ── get_guide — 3 언어 분기 ──────────────────────────────────────────────


@pytest.mark.parametrize("lang", _TIER1)
def test_tier1_full_english_default(lang):
    """Tier1 10 언어 — FULL 영문 (default) 반환 + Korean 텍스트 부재."""
    guide = get_guide(lang, "full", output_language="en")
    assert isinstance(guide, str)
    assert len(guide) > 50
    # 영문 default = ASCII 위주 (한국어 영역 없어야 함)
    # English default = ASCII-only (no Korean)
    assert "검토 기준" not in guide  # Korean header absent
    assert "review checklist" in guide.lower() or "review" in guide.lower()


@pytest.mark.parametrize("lang", _TIER1)
def test_tier1_full_korean(lang):
    """Tier1 10 언어 — FULL 한국어 반환."""
    guide = get_guide(lang, "full", output_language="ko")
    assert isinstance(guide, str)
    assert len(guide) > 50
    # 한국어 가이드 헤더 (lang 별 다른 한국어 이름)
    assert "검토 기준" in guide  # Korean header present


@pytest.mark.parametrize("lang", _TIER1)
def test_tier1_full_japanese(lang):
    """Tier1 10 언어 — FULL 일본어 반환."""
    guide = get_guide(lang, "full", output_language="ja")
    assert isinstance(guide, str)
    assert len(guide) > 50
    # 일본어 가이드 헤더
    assert "レビュー基準" in guide  # Japanese header present


@pytest.mark.parametrize("lang", _TIER1)
def test_tier1_compact_3_languages_distinct(lang):
    """Tier1 10 언어 — COMPACT 3 언어 모두 다른 텍스트 (cache key 분기 검증)."""
    en = get_guide(lang, "compact", output_language="en")
    ko = get_guide(lang, "compact", output_language="ko")
    ja = get_guide(lang, "compact", output_language="ja")
    assert en != ko
    assert en != ja
    assert ko != ja


def test_get_guide_default_output_language_is_english():
    """get_guide — output_language default = 'en'."""
    en_explicit = get_guide("python", "full", output_language="en")
    en_default = get_guide("python", "full")
    assert en_explicit == en_default


def test_get_guide_invalid_output_language_falls_to_english():
    """invalid output_language → 영문 fallback."""
    en = get_guide("python", "full", output_language="en")
    invalid = get_guide("python", "full", output_language="zh")  # 미지원
    assert en == invalid


def test_get_guide_unknown_language_uses_generic_fallback():
    """unknown language → generic.py fallback (영문)."""
    guide = get_guide("unknown_lang_xyz", "full", output_language="ko")
    assert isinstance(guide, str)
    assert len(guide) > 10


# ── Tier2/3 영문 fallback (PR-14/15 별도 진행 영역) ─────────────────────────


def test_tier2_now_supports_korean_after_pr14():
    """Tier2 (php) — PR-14 적용 후 한국어 지원 (영문/한국어/일본어 distinct)."""
    en = get_guide("php", "full", output_language="en")
    ko = get_guide("php", "full", output_language="ko")
    ja = get_guide("php", "full", output_language="ja")
    # Phase 4 PR-14 적용 후 — Tier2 도 다국어 지원
    assert en != ko
    assert en != ja
    assert ko != ja


def test_tier3_now_supports_japanese_after_pr15():
    """Tier3 (julia) — PR-15 적용 후 일본어 지원 (영문/한국어/일본어 distinct)."""
    en = get_guide("julia", "full", output_language="en")
    ja = get_guide("julia", "full", output_language="ja")
    # Phase 4 PR-15 적용 후 — Tier3 도 다국어 지원
    assert en != ja


# ── build_review_prompt + build_review_blocks — language 전달 ─────────────


def _patches() -> list[tuple[str, str]]:
    return [("app.py", "+def hello():\n+    return 'hi'")]


def test_build_review_prompt_korean_lang_guides():
    """build_review_prompt(language='ko') → Tier1 가이드 한국어로 inline 포함."""
    user_prompt, languages = build_review_prompt("commit msg", _patches(), language="ko")
    assert "python" in languages
    # 한국어 가이드 inline 포함
    assert "Python 검토 기준" in user_prompt


def test_build_review_prompt_japanese_lang_guides():
    """build_review_prompt(language='ja') → Tier1 가이드 일본어로 inline 포함."""
    user_prompt, languages = build_review_prompt("commit msg", _patches(), language="ja")
    assert "python" in languages
    assert "Python レビュー基準" in user_prompt


def test_build_review_prompt_english_default():
    """build_review_prompt() default → Tier1 가이드 영문."""
    user_prompt, _ = build_review_prompt("commit msg", _patches())
    assert "Python review checklist" in user_prompt


def test_build_review_blocks_korean():
    """build_review_blocks(language='ko') → lang_guides_block 한국어."""
    lang_block, user_prompt, languages = build_review_blocks(
        "commit msg", _patches(), language="ko",
    )
    assert "python" in languages
    if lang_block:
        assert "Python 검토 기준" in lang_block
        # User prompt 안 lang_guides 비움 (multi-block 분리)
        assert "Python 검토 기준" not in user_prompt


# ── 영문 텍스트 무결성 검증 — Tier1 10 언어 모두 'review checklist' 영문 헤더 ─


@pytest.mark.parametrize("lang", _TIER1)
def test_tier1_english_full_has_review_checklist_header(lang):
    """Tier1 10 언어 영문 FULL — `review checklist` 헤더 의무 (일관성 보장)."""
    guide = get_guide(lang, "full", output_language="en")
    assert "review checklist" in guide.lower()


@pytest.mark.parametrize("lang", _TIER1)
def test_tier1_korean_full_has_review_header(lang):
    """Tier1 10 언어 한국어 FULL — `검토 기준` 헤더 의무."""
    guide = get_guide(lang, "full", output_language="ko")
    assert "검토 기준" in guide


@pytest.mark.parametrize("lang", _TIER1)
def test_tier1_japanese_full_has_review_header(lang):
    """Tier1 10 언어 일본어 FULL — `レビュー基準` 헤더 의무."""
    guide = get_guide(lang, "full", output_language="ja")
    assert "レビュー基準" in guide


def test_supported_languages_unchanged():
    """supported_languages — 50 언어 보존 (i18n 적용 후 변경 0)."""
    assert len(supported_languages()) == 50
