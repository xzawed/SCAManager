"""tests/unit/gate/test_merge_failure_advisor.py"""
import pytest
from src.gate import merge_reasons


def test_get_advice_known_reason_returns_specific_text():
    """알려진 reason tag 는 태그별 권장 조치 텍스트를 반환한다."""
    from src.gate.merge_failure_advisor import get_advice
    advice = get_advice(merge_reasons.BRANCH_PROTECTION_BLOCKED)
    assert "Branch Protection" in advice


def test_get_advice_with_colon_suffix_extracts_tag():
    """engine 이 'tag: user-facing text' 형식으로 전달해도 태그 부분만 추출해 매핑한다."""
    from src.gate.merge_failure_advisor import get_advice
    full_reason = f"{merge_reasons.DIRTY_CONFLICT}: 머지 조건 미충족 (state=dirty)"
    advice = get_advice(full_reason)
    assert "충돌" in advice


def test_get_advice_unknown_or_none_returns_default():
    """알 수 없는 태그와 None 은 기본 문구를 반환한다."""
    from src.gate.merge_failure_advisor import get_advice, _DEFAULT_ADVICE
    assert get_advice("completely_unknown_tag") == _DEFAULT_ADVICE
    assert get_advice(None) == _DEFAULT_ADVICE
