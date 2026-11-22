"""리뷰 호출이 공용 도우미를 거친다 — 거절 · Haiku→Sonnet · effort · 시도마다 비용 행 하나 (Issue #1905 ①b).

The review call goes through the shared helper: refusals, Haiku-to-Sonnet, effort and one cost row per attempt.
응답은 SDK 의 실제 타입(Message)으로 만든다 — 거절 응답은 본문이 비어 있다.
Responses are real SDK Message objects; a refusal comes back with no content.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

from anthropic.types import Message

from src.analyzer.io.ai_review import review_code
from src.config import settings
from src.scorer.reliability import score_is_unreliable

_REVIEW_JSON = json.dumps({"commit_message_score": 18, "direction_score": 17, "test_score": 10,
                           "summary": "ok", "suggestions": []})


def _message(*, model: str, stop_reason: str = "end_turn", text: str | None = _REVIEW_JSON) -> Message:
    return Message.model_validate({
        "id": "msg", "type": "message", "role": "assistant", "model": model,
        "content": [{"type": "text", "text": text}] if text is not None else [],
        "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 5, "cache_read_input_tokens": 0,
                  "cache_creation_input_tokens": 0},
    })


async def _review(responses, *, model, effort=None):
    client = MagicMock()
    client.messages.create = AsyncMock(side_effect=list(responses))
    with patch("src.analyzer.io.ai_review.new_async_anthropic", return_value=client), \
         patch("src.analyzer.io.ai_review.aclose_anthropic_client", AsyncMock()), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as cost_row:
        result = await review_code("sk-test", "feat: add", [("app.py", "+ x = 1")], model=model, repo_id=7,
                                   effort=effort)
    rows = [(c.kwargs["model"], c.kwargs["status"], c.kwargs.get("error_type", ""), c.kwargs["repo_id"])
            for c in cost_row.call_args_list]
    return result, rows, [c.kwargs for c in client.messages.create.await_args_list]


async def test_refused_review_is_a_failed_review_with_a_refusal_cause():
    # 거절 = 리뷰가 없다 — 새 상태 없이 기존 실패(api_error) · 원인 라벨 refused · 점수는 신뢰 불가
    # A refusal means no review: the existing failure status, a refused cause label, an unreliable score.
    result, rows, _ = await _review([_message(model="claude-sonnet-5", stop_reason="refusal", text=None)],
                                    model="claude-sonnet-5")
    assert (result.status, result.error_derived_cause, result.error_type) == ("api_error", "refused", None)
    assert score_is_unreliable({"ai_review_status": result.status})
    assert rows == [("claude-sonnet-5", "refused", "", 7)]


async def test_haiku_refusal_review_is_answered_by_sonnet():
    result, rows, calls = await _review([
        _message(model="claude-haiku-4-5", stop_reason="refusal", text=None),
        _message(model="claude-sonnet-5"),
    ], model="claude-haiku-4-5")
    assert (result.status, result.used_model) == ("success", "claude-sonnet-5")
    assert [call["model"] for call in calls] == ["claude-haiku-4-5", "claude-sonnet-5"]
    assert rows == [("claude-haiku-4-5", "refused", "", 7), ("claude-sonnet-5", "success", "", 7)]


async def test_review_sends_the_configured_effort_only_where_supported(monkeypatch):
    monkeypatch.setattr(settings, "claude_call_effort", "medium")
    _, _, sonnet_calls = await _review([_message(model="claude-sonnet-5")], model="claude-sonnet-5")
    _, _, haiku_calls = await _review([_message(model="claude-haiku-4-5")], model="claude-haiku-4-5")
    assert sonnet_calls[0]["output_config"]["effort"] == "medium"
    assert "effort" not in haiku_calls[0]["output_config"]


async def test_a_fallback_served_review_writes_one_row_per_hop_and_names_the_answering_model():
    # 서버 대체가 답한 리뷰 — 거절한 판 · 답한 판이 각자 행 하나(그 판의 토큰) · used_model 은 답한 판
    # A review answered by a server fallback: one row per hop with that hop's tokens; used_model is the answerer.
    from anthropic.types.beta import BetaMessage  # pylint: disable=import-outside-toplevel

    from src.shared import model_catalog as mc  # pylint: disable=import-outside-toplevel

    mc.install_snapshot([mc.ModelEntry(
        id="claude-sonnet-5", line="sonnet", display_name="Sonnet 5", created_at=mc.FALLBACK_CATALOG[0].created_at,
        deprecated_at=None, retires_at=None, supports_structured_outputs=True, supports_effort=True,
        server_fallback=True)], source="api")
    hops = [{"type": "message", "model": None, "input_tokens": 40, "output_tokens": 0,
             "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
            {"type": "fallback_message", "model": "claude-opus-5", "input_tokens": 45, "output_tokens": 30,
             "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}]
    answered = BetaMessage.model_validate({
        "id": "msg", "type": "message", "role": "assistant", "model": "claude-opus-5",
        "content": [{"type": "text", "text": _REVIEW_JSON}], "stop_reason": "end_turn", "stop_sequence": None,
        "usage": {"input_tokens": 45, "output_tokens": 30, "iterations": hops},
    })
    client = MagicMock()
    client.beta.messages.create = AsyncMock(return_value=answered)
    with patch("src.analyzer.io.ai_review.new_async_anthropic", return_value=client), \
         patch("src.analyzer.io.ai_review.aclose_anthropic_client", AsyncMock()), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as cost_row:
        result = await review_code("sk-test", "feat: add", [("app.py", "+ x = 1")], model="claude-sonnet-5")
    assert (result.status, result.used_model) == ("success", "claude-opus-5")
    assert [(c.kwargs["model"], c.kwargs["status"], c.kwargs["input_tokens"]) for c in cost_row.call_args_list] == [
        ("claude-sonnet-5", "refused", 40), ("claude-opus-5", "success", 45)]


async def test_the_repo_effort_wins_over_the_global_setting(monkeypatch):
    # 리포가 고른 단계가 먼저 · 비우면 운영 변수 / the repo's level first, else the global setting
    monkeypatch.setattr(settings, "claude_call_effort", "high")
    _, _, repo_calls = await _review([_message(model="claude-sonnet-5")], model="claude-sonnet-5", effort="low")
    _, _, global_calls = await _review([_message(model="claude-sonnet-5")], model="claude-sonnet-5")
    assert repo_calls[0]["output_config"]["effort"] == "low"
    assert global_calls[0]["output_config"]["effort"] == "high"
