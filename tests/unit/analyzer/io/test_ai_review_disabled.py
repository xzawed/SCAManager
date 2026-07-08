"""AI_REVIEW_DISABLED / enabled=False 시 Anthropic 호출 없이 disabled 반환 검증.
Verify no Anthropic call + disabled status when the AI review is switched off."""
import asyncio
from unittest.mock import patch
from src.analyzer.io.ai_review import review_code

_PATCHES = [("a.py", "@@ -1 +1 @@\n-x\n+y")]


def test_enabled_false_returns_disabled_without_api_call():
    # enabled=False → 클라이언트 생성 자체가 없어야 함 (비용 0)
    # enabled=False → the client must never be instantiated (zero cost)
    with patch("anthropic.AsyncAnthropic") as mock_client:
        result = asyncio.run(
            review_code("sk-live-key", "msg", _PATCHES, enabled=False)
        )
    assert result.status == "disabled"
    mock_client.assert_not_called()


def test_env_ai_review_disabled_returns_disabled(monkeypatch):
    monkeypatch.setenv("AI_REVIEW_DISABLED", "1")
    with patch("anthropic.AsyncAnthropic") as mock_client:
        result = asyncio.run(review_code("sk-live-key", "msg", _PATCHES))
    assert result.status == "disabled"
    mock_client.assert_not_called()


def test_disabled_precedes_no_api_key(monkeypatch):
    # 전역 비활성 시 키 없어도 status=disabled (no_api_key 아님) — 우선순위 검증
    monkeypatch.setenv("AI_REVIEW_DISABLED", "1")
    result = asyncio.run(review_code("", "msg", _PATCHES))
    assert result.status == "disabled"
