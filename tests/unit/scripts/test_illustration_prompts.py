"""사이클 93 Step 2 회귀 가드 — UI 일러스트 5장 prompt 정의 보존.

Cycle 93 Step 2 regression guards — preserve 5 UI illustration prompt definitions.

정책 4 페어 (단언 + 회귀 가드 동시 머지) — 사용자 결정 영역 (5장 placement / isometric
스타일 / 4-테마 호환) 의 잠재 회귀 차단.
"""
from __future__ import annotations

import pytest

from src.scripts.illustration_prompts import PROMPTS, IllustrationPrompt, get_prompt


# ─── 사용자 결정 영역 보존 ─────────────────────────────────────────────────


def test_prompt_count_is_five():
    """사용자 결정 = 5장 (login / dashboard empty / overview / add_repo / filter empty).

    User decision = 5 illustrations. 404 페이지 = 별도 PR (사용자 OK).
    """
    assert len(PROMPTS) == 5, f"prompt 개수 5장 의무 (실측 {len(PROMPTS)}장)"


def test_prompt_names_match_user_decided_placements():
    """사용자 결정 5장 placement 이름 보존 — 변경 시 별도 PR + 사용자 사전 확인 의무."""
    expected = {
        "login_hero",
        "dashboard_empty",
        "overview_onboarding",
        "add_repo_hero",
        "filter_empty",
    }
    actual = {p.name for p in PROMPTS}
    assert actual == expected, f"placement 이름 mismatch: 추가={actual - expected}, 누락={expected - actual}"


def test_all_prompts_specify_isometric_style():
    """사용자 결정 2 (★) = Abstract isometric data flows. 5장 모두 isometric 명시 의무."""
    for p in PROMPTS:
        assert "isometric" in p.prompt.lower(), (
            f"{p.name}: 'isometric' 키워드 누락 — 사용자 결정 2 (★) 위반"
        )


def test_all_prompts_exclude_text_letters_numbers():
    """텍스트/letters/numbers 명시 제외 의무 — Crimson Pro 한글 미호환 학습 + DALL-E
    텍스트 렌더링 정확도 ↓ + 4-테마 통합 시 텍스트 색 충돌 회피.
    """
    for p in PROMPTS:
        text = p.prompt.lower()
        assert "no text" in text or "no letters" in text, (
            f"{p.name}: 'no text/letters' 명시 누락"
        )
        assert "no numbers" in text or "no readable" in text, (
            f"{p.name}: 'no numbers/readable' 명시 누락"
        )


def test_all_prompts_compatible_with_4_themes():
    """4-테마 호환 = warm cream + dark indigo + glass + claude-dark 모두 동작.
    공통 톤 가이드 (_COMMON_STYLE) 가 'neutral background' 명시.
    """
    for p in PROMPTS:
        assert "neutral background" in p.prompt.lower(), (
            f"{p.name}: 4-테마 호환을 위한 'neutral background' 누락"
        )


# ─── DALL-E 3 API 사양 정합 ────────────────────────────────────────────────


def test_dalle3_size_options_valid():
    """DALL-E 3 지원 size: 1024×1024 / 1792×1024 / 1024×1792 만 허용."""
    valid_sizes = {"1024x1024", "1792x1024", "1024x1792"}
    for p in PROMPTS:
        assert p.size in valid_sizes, (
            f"{p.name}: DALL-E 3 미지원 size {p.size!r}"
        )


def test_dalle3_quality_options_valid():
    """DALL-E 3 quality: 'standard' (저비용) | 'hd' (2배) 만 허용."""
    for p in PROMPTS:
        assert p.quality in ("standard", "hd"), (
            f"{p.name}: 미지원 quality {p.quality!r}"
        )


def test_prompt_under_dalle3_max_4000_chars():
    """DALL-E 3 prompt 최대 4000 chars (2026-05 기준) — 초과 시 API 거절."""
    for p in PROMPTS:
        assert len(p.prompt) < 4000, (
            f"{p.name}: prompt {len(p.prompt)} chars (4000 미만 의무)"
        )


# ─── API 표면 가드 ─────────────────────────────────────────────────────────


def test_get_prompt_returns_correct_dataclass():
    """get_prompt(name) 정확히 일치 반환."""
    p = get_prompt("login_hero")
    assert isinstance(p, IllustrationPrompt)
    assert p.name == "login_hero"


def test_get_prompt_raises_keyerror_for_unknown():
    """미정의 이름 = KeyError (silent None 반환 금지 — 정책 16 정확성)."""
    with pytest.raises(KeyError):
        get_prompt("nonexistent_name")
