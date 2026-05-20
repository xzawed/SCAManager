"""dashboard_service._INSIGHT_SYSTEM_PROMPT 언어 중립화 검증.

Verifies that the system prompt no longer contains Korean-language-specific
hardcoded instructions, ensuring language-neutral phrasing after the refactor.

Target lines (before fix):
  625: "is the metric name in Korean (e.g. 평균 점수)."
  634: "Each list item ≤ 80 Korean characters."
  635: "Use full sentences ending with appropriate Korean particles."
"""
from __future__ import annotations

import pytest


# ─── _INSIGHT_SYSTEM_PROMPT 언어 중립화 검증 ────────────────────────────────


def _get_system_prompt() -> str:
    """dashboard_service 모듈에서 _INSIGHT_SYSTEM_PROMPT 문자열을 추출.

    Extracts the _INSIGHT_SYSTEM_PROMPT constant from dashboard_service.
    """
    import src.services.dashboard_service as m

    assert hasattr(m, "_INSIGHT_SYSTEM_PROMPT"), (
        "_INSIGHT_SYSTEM_PROMPT constant not found in dashboard_service."
    )
    return m._INSIGHT_SYSTEM_PROMPT  # type: ignore[attr-defined]


def test_system_prompt_no_korean_label_instruction():
    """_INSIGHT_SYSTEM_PROMPT에 'in Korean (e.g.' 구절이 없어야 함.

    The phrase 'in Korean (e.g.' must be removed from the system prompt.
    Current (Red): 'is the metric name in Korean (e.g. 평균 점수).'
    Target (Green): 'is the metric name in the response language.'
    """
    prompt = _get_system_prompt()

    assert "in Korean (e.g." not in prompt, (
        "_INSIGHT_SYSTEM_PROMPT still contains 'in Korean (e.g.' — "
        "replace with 'in the response language.'"
    )


def test_system_prompt_no_korean_characters():
    """_INSIGHT_SYSTEM_PROMPT에 'Korean characters' 구절이 없어야 함.

    The phrase 'Korean characters' must be removed from the system prompt.
    Current (Red): 'Each list item ≤ 80 Korean characters.'
    Target (Green): 'Each list item ≤ 80 characters.'
    """
    prompt = _get_system_prompt()

    assert "Korean characters" not in prompt, (
        "_INSIGHT_SYSTEM_PROMPT still contains 'Korean characters' — "
        "replace with '80 characters.' (language-neutral)."
    )


def test_system_prompt_no_korean_particles():
    """_INSIGHT_SYSTEM_PROMPT에 'Korean particles' 구절이 없어야 함.

    The phrase 'Korean particles' must be removed from the system prompt.
    Current (Red): 'Use full sentences ending with appropriate Korean particles.'
    Target (Green): 'Use full sentences.'
    """
    prompt = _get_system_prompt()

    assert "Korean particles" not in prompt, (
        "_INSIGHT_SYSTEM_PROMPT still contains 'Korean particles' — "
        "replace with 'Use full sentences.' (language-neutral)."
    )


def test_system_prompt_retains_structure_fields():
    """언어 중립화 후에도 JSON 구조 필드 지시(positive_highlights 등)는 보존되어야 함.

    Removing Korean-specific phrases must not accidentally remove the
    JSON schema instructions that callers depend on.
    """
    prompt = _get_system_prompt()

    # JSON 스키마 필드 4개가 여전히 존재하는지 확인 (회귀 방지)
    # Verify the four JSON schema fields remain after the edit (regression guard).
    for field in ("positive_highlights", "focus_areas", "key_metrics", "next_actions"):
        assert field in prompt, (
            f"_INSIGHT_SYSTEM_PROMPT lost required JSON field '{field}' "
            "during the language-neutral refactor."
        )


def test_system_prompt_language_neutral_replacement_present():
    """언어 중립 대체 구절 'response language'가 삽입되어 있어야 함.

    After the fix, the prompt must contain 'response language' to indicate
    language-neutral instruction.
    Current (Red): phrase absent.
    Target (Green): 'is the metric name in the response language.'
    """
    prompt = _get_system_prompt()

    assert "response language" in prompt, (
        "_INSIGHT_SYSTEM_PROMPT is missing 'response language' — "
        "the Korean-neutral replacement phrase has not been added yet."
    )
