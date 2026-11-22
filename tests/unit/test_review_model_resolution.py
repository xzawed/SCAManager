"""리뷰 모델 선택이 카탈로그 해석을 거친다 — auto:<line> · 판 고정 · 기본값 · 읽을 수 없는 저장값 (Issue #1905 ①a Task 4).

Review model selection goes through the catalog resolver: line values, pinned ids, the default and unreadable values.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.analyzer.io.ai_review import review_code
from src.config import settings
from src.shared import model_catalog as mc

_REVIEW_JSON = json.dumps({"commit_message_score": 18, "direction_score": 17, "test_score": 10,
                           "summary": "ok", "suggestions": []})


async def _review(model):
    """review_code 한 번 — (create 에 넘긴 모델, 비용 행의 모델, 결과) / one review: (create model, cost-row model, result)."""
    block = MagicMock()
    block.type = "text"
    block.text = _REVIEW_JSON
    response = MagicMock()
    response.content = [block]
    response.stop_reason = "end_turn"
    response.usage = MagicMock(input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
                               cache_creation_input_tokens=0)
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=response)
    with patch("src.analyzer.io.ai_review.new_async_anthropic", return_value=client), \
         patch("src.analyzer.io.ai_review.aclose_anthropic_client", AsyncMock()), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as cost_row:
        result = await review_code("sk-test", "feat: add", [("app.py", "+ x = 1")], model=model)
    return client.messages.create.await_args.kwargs["model"], cost_row.call_args.kwargs["model"], result


async def test_review_code_calls_resolved_model():
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    called, logged, result = await _review("auto:haiku")
    assert (called, logged, result.used_model) == ("claude-haiku-5-5", "claude-haiku-5-5", "claude-haiku-5-5")


async def test_pinned_value_passes_through():
    called, logged, _ = await _review("claude-opus-5")
    assert (called, logged) == ("claude-opus-5", "claude-opus-5")


async def test_default_value_is_resolved_too(monkeypatch):
    monkeypatch.setattr(settings, "claude_review_model", "auto:sonnet")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    called, _, _ = await _review(None)
    assert called == "claude-sonnet-5-5"


async def test_unreadable_stored_value_uses_the_default(monkeypatch):
    # 저장 검증 전에 남은 값(모르는 계열) — 리뷰가 깨지지 않고 기본값으로 부른다.
    # A value saved before save-time validation existed: the review falls back instead of crashing.
    monkeypatch.setattr(settings, "claude_review_model", "claude-sonnet-5")
    called, _, result = await _review("auto:gpt")
    assert (called, result.status) == ("claude-sonnet-5", "success")
