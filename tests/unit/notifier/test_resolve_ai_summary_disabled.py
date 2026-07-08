"""resolve_ai_summary: disabled 상태는 'AI 불가'가 아니라 '설정으로 비활성' 메시지.

disabled → a distinct 'turned off by config' message, not the generic 'unavailable'.
"""
from types import SimpleNamespace

from src.i18n.loader import get_text
from src.notifier._common import resolve_ai_summary


def test_disabled_returns_distinct_message():
    ai = SimpleNamespace(status="disabled", summary="ignored")
    msg = resolve_ai_summary(ai, "ko")
    assert msg  # 비어있지 않음
    # ai_unavailable 과 다른 메시지여야 함 (disabled 전용 키)
    assert msg == get_text("notifier.common.ai_disabled", "ko")
    assert msg != get_text("notifier.common.ai_unavailable", "ko")


def test_api_error_still_unavailable():
    # 회귀 가드 — 실패 status 는 여전히 generic ai_unavailable
    ai = SimpleNamespace(status="api_error", summary="ignored")
    assert resolve_ai_summary(ai, "ko") == get_text("notifier.common.ai_unavailable", "ko")


def test_success_returns_summary():
    ai = SimpleNamespace(status="success", summary="좋은 코드")
    assert resolve_ai_summary(ai, "ko") == "좋은 코드"
