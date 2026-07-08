"""disabled 상태는 genuine 실패 아님 — auto-merge 미차단 + 점수 NULL 아님 보존.
disabled must NOT be a genuine failure (auto-merge allowed, score not NULLed)."""
from src.gate._common import ai_review_failed, AI_REVIEW_FAILED_STATUSES


def test_disabled_is_not_a_failure():
    assert ai_review_failed({"ai_review_status": "disabled"}) is False


def test_disabled_absent_from_failed_statuses():
    # 회귀 가드 — 누군가 disabled 를 실패군에 넣으면 auto-merge 영구 차단(잘못).
    assert "disabled" not in AI_REVIEW_FAILED_STATUSES
    assert AI_REVIEW_FAILED_STATUSES == frozenset({"api_error", "parse_error"})
