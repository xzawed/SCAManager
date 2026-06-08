"""src/gate/_common.py 헬퍼 단위 테스트.
Unit tests for the src/gate/_common.py helpers.
"""
import pytest

from src.gate._common import AI_REVIEW_FAILED_STATUSES, ai_review_failed


@pytest.mark.parametrize("status", ["api_error", "parse_error"])
def test_ai_review_failed_true_for_genuine_failures(status):
    """API 호출/JSON 파싱 오류는 genuine 실패 → True (auto-merge/approve 차단 대상).
    API/parse errors are genuine failures → True (block auto actions).
    """
    assert ai_review_failed({"ai_review_status": status}) is True


@pytest.mark.parametrize("status", ["success", "no_api_key", "empty_diff"])
def test_ai_review_failed_false_for_success_and_intentional_skips(status):
    """정상·의도적 미수행(no_api_key/empty_diff)은 차단 대상 아님 → False (기존 동작 보존).
    Success and intentional skips are not failures → False (preserves existing behavior).
    """
    assert ai_review_failed({"ai_review_status": status}) is False


def test_ai_review_failed_false_when_status_missing():
    """ai_review_status 키 부재(구 레코드) 시 False — 안전 기본값(차단 안 함).
    Missing key (legacy records) → False — safe default that does not block.
    """
    assert ai_review_failed({"score": 90}) is False


def test_ai_failed_statuses_excludes_intentional_skips():
    """상수 집합은 genuine 실패만 포함 — no_api_key/empty_diff/success 제외 (회귀 가드).
    The status set contains only genuine failures — excludes intentional skips (regression guard).
    """
    assert AI_REVIEW_FAILED_STATUSES == frozenset({"api_error", "parse_error"})
    assert "no_api_key" not in AI_REVIEW_FAILED_STATUSES
    assert "empty_diff" not in AI_REVIEW_FAILED_STATUSES
    assert "success" not in AI_REVIEW_FAILED_STATUSES
