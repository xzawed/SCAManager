"""공용 Claude 호출 도우미 — 판 해석 · effort · 서버 대체 · 안전 거절 · Haiku→Sonnet · 새 판 거부 대체 (Issue #1905 ①b).

The shared Claude call helper: resolution, effort, server fallback, refusals, Haiku-to-Sonnet and rejection fallback.
가짜는 바깥 경계(Anthropic 클라이언트 · 비용 행 기록)에만 둔다 — 응답은 SDK 의 실제 타입으로 만든다.
Fakes sit only at the outer boundaries; responses are built from the SDK's real types.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from anthropic.types import Message
from anthropic.types.beta import BetaMessage

from src.config import settings
from src.shared import claude_call as cc
from src.shared import model_catalog as mc

_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
_SYSTEM = [{"type": "text", "text": "Reply with JSON."}]
_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
_MESSAGES = [{"role": "user", "content": "x"}]


def _d(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _entry(model_id: str, line: str, *, effort: bool = True, server_fallback: bool | None = None,
           created: datetime | None = None) -> mc.ModelEntry:
    return mc.ModelEntry(id=model_id, line=line, display_name=model_id, created_at=created or _d(2026, 10, 1),
                         deprecated_at=None, retires_at=None, supports_structured_outputs=True,
                         supports_effort=effort, server_fallback=server_fallback)


def _usage(**extra) -> dict:
    return {"input_tokens": 12, "output_tokens": 5, "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0, **extra}


def _message(*, model: str, stop_reason: str = "end_turn", text: str | None = '{"ok": true}'):
    content = [{"type": "text", "text": text}] if text is not None else []
    return Message.construct(id="msg", type="message", role="assistant", model=model, content=content,
                             stop_reason=stop_reason, stop_sequence=None, usage=_usage())


def _beta_message(*, model: str, stop_reason: str = "end_turn", iterations=None):
    return BetaMessage.construct(id="msg", type="message", role="assistant", model=model,
                                 content=[{"type": "text", "text": '{"ok": true}'}], stop_reason=stop_reason,
                                 stop_sequence=None, usage=_usage(iterations=iterations))


def _status_error(cls, code: int):
    return cls("call failed", response=httpx.Response(code, request=_REQUEST), body=None)


class _FakeCreate:
    def __init__(self, outcomes):
        self.calls = []
        self._outcomes = list(outcomes)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _client(*, plain=(), beta=()):
    return SimpleNamespace(messages=_FakeCreate(plain), beta=SimpleNamespace(messages=_FakeCreate(beta)))


@pytest.fixture
def rows():
    collected = []

    async def _record(**row):
        collected.append(row)

    return SimpleNamespace(rows=collected, record=_record)


async def _call(client, rows, value, *, default="claude-sonnet-5"):
    return await cc.create_json_message(client, model_value=value, default_value=default, max_tokens=256,
                                        system=_SYSTEM, schema=_SCHEMA, messages=_MESSAGES, record=rows.record)


def _row_view(rows):
    return [(row["model"], row["status"], row["error_type"]) for row in rows.rows]


async def test_refusal_is_detected_before_reading_the_content(rows):
    client = _client(plain=[_message(model="claude-sonnet-5", stop_reason="refusal", text=None)])
    outcome = await _call(client, rows, "claude-sonnet-5")
    assert (outcome.refused, outcome.fallback_served, outcome.model) == (True, False, "claude-sonnet-5")
    # 마지막 응답의 행은 호출부 몫 — 도우미는 앞선 시도만 적는다 / the final row belongs to the caller
    assert rows.rows == []


async def test_server_fallback_goes_only_where_the_listing_allows_it(rows):
    mc.install_snapshot([_entry("claude-sonnet-5-5", "sonnet", server_fallback=True),
                         _entry("claude-sonnet-5", "sonnet", server_fallback=False, created=_d(2026, 4, 1))],
                        source="api")
    client = _client(plain=[_message(model="claude-sonnet-5")], beta=[_beta_message(model="claude-sonnet-5-5")])
    await _call(client, rows, "claude-sonnet-5-5")
    await _call(client, rows, "claude-sonnet-5")
    (beta_call,) = client.beta.messages.calls[:1]
    assert (beta_call["model"], beta_call["betas"], beta_call["fallbacks"]) == (
        "claude-sonnet-5-5", ["server-side-fallback-2026-07-01"], "default")
    (plain_call,) = client.messages.calls[:1]
    assert plain_call["model"] == "claude-sonnet-5" and "fallbacks" not in plain_call


async def test_served_model_follows_the_response_when_a_fallback_answered(rows):
    mc.install_snapshot([_entry("claude-sonnet-5-5", "sonnet", server_fallback=True)], source="api")
    iterations = [{"type": "message", "model": None, "input_tokens": 9, "output_tokens": 1,
                   "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
                  {"type": "fallback_message", "model": "claude-opus-5", "input_tokens": 12, "output_tokens": 5,
                   "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}]
    client = _client(beta=[_beta_message(model="claude-opus-5", iterations=iterations)])
    outcome = await _call(client, rows, "claude-sonnet-5-5")
    assert (outcome.model, outcome.fallback_served, outcome.refused) == ("claude-opus-5", True, False)
    # 서버 대체가 돈 응답은 hop 마다 한 행 — 거절한 판 · 답한 판이 각자 토큰을 낸다
    # A response with a server fallback writes one row per hop; each hop bills its own tokens.
    await cc.record_response(rows.record, outcome.response, model=outcome.requested, duration_ms=50.0,
                             status="success")
    assert [(r["model"], r["status"], r["input_tokens"]) for r in rows.rows] == [
        ("claude-sonnet-5-5", "refused", 9), ("claude-opus-5", "success", 12)]


async def test_record_response_writes_one_row_without_iterations(rows):
    await cc.record_response(rows.record, _message(model="claude-sonnet-5"), model="claude-sonnet-5",
                             duration_ms=10.0, status="success")
    assert rows.rows == [{"model": "claude-sonnet-5", "duration_ms": 10.0, "status": "success", "error_type": "",
                          "input_tokens": 12, "output_tokens": 5, "cache_read_tokens": 0, "cache_creation_tokens": 0}]


async def test_haiku_refusal_retries_on_the_verified_sonnet(rows):
    mc.install_snapshot([_entry("claude-haiku-4-5", "haiku", effort=False, created=_d(2025, 10, 1)),
                         _entry("claude-sonnet-5-5", "sonnet", server_fallback=True)], source="api")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    client = _client(plain=[_message(model="claude-haiku-4-5", stop_reason="refusal", text=None)],
                     beta=[_beta_message(model="claude-sonnet-5-5")])
    outcome = await _call(client, rows, "claude-haiku-4-5")
    assert (outcome.model, outcome.refused) == ("claude-sonnet-5-5", False)
    assert client.beta.messages.calls[0]["fallbacks"] == "default"
    assert _row_view(rows) == [("claude-haiku-4-5", "refused", "")]


async def test_haiku_refusal_without_a_verified_sonnet_uses_the_fallback_default(rows):
    client = _client(plain=[_message(model="claude-haiku-4-5", stop_reason="refusal", text=None),
                            _message(model="claude-sonnet-5")])
    outcome = await _call(client, rows, "claude-haiku-4-5")
    assert [call["model"] for call in client.messages.calls] == ["claude-haiku-4-5", "claude-sonnet-5"]
    assert outcome.model == "claude-sonnet-5"


async def test_whole_chain_refusal_reports_refused(rows):
    client = _client(plain=[_message(model="claude-haiku-4-5", stop_reason="refusal", text=None),
                            _message(model="claude-sonnet-5", stop_reason="refusal", text=None)])
    outcome = await _call(client, rows, "claude-haiku-4-5")
    assert (outcome.refused, outcome.model) == (True, "claude-sonnet-5")


async def test_auto_model_400_moves_to_the_previous_model_and_marks_it_failed(rows):
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400), _message(model="claude-haiku-4-5")])
    outcome = await _call(client, rows, "auto:haiku")
    assert outcome.model == "claude-haiku-4-5"
    assert mc.is_failed("claude-haiku-5-5")
    assert _row_view(rows) == [("claude-haiku-5-5", "error", "model_rejected")]


async def test_auto_via_the_default_value_counts_as_auto(rows):
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400), _message(model="claude-haiku-4-5")])
    outcome = await _call(client, rows, None, default="auto:haiku")
    assert outcome.model == "claude-haiku-4-5" and mc.is_failed("claude-haiku-5-5")


async def test_auto_model_400_is_not_marked_when_the_previous_model_also_fails(rows):
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    first = _status_error(anthropic.BadRequestError, 400)
    client = _client(plain=[first, _status_error(anthropic.BadRequestError, 400)])
    with pytest.raises(anthropic.BadRequestError) as caught:
        await _call(client, rows, "auto:haiku")
    # 둘 다 400 = 계정 · 요청 쪽(지출 한도 등) — 판 탓이 아니다 · 올리는 것은 첫 오류다
    # Both 400: an account/request problem (e.g. a spend limit), not the model; the first error is raised.
    assert caught.value is first
    assert not mc.is_failed("claude-haiku-5-5")
    assert _row_view(rows) == [("claude-haiku-5-5", "error", "BadRequestError"),
                               ("claude-haiku-4-5", "error", "BadRequestError")]


async def test_pinned_model_400_is_not_retried(rows):
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400)])
    with pytest.raises(anthropic.BadRequestError):
        await _call(client, rows, "claude-sonnet-5")
    assert len(client.messages.calls) == 1
    assert _row_view(rows) == [("claude-sonnet-5", "error", "BadRequestError")]


@pytest.mark.parametrize("error", [
    _status_error(anthropic.RateLimitError, 429),
    _status_error(anthropic.InternalServerError, 500),
    anthropic.APIConnectionError(message="down", request=_REQUEST),
])
async def test_transient_errors_are_not_retried(rows, error):
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    client = _client(plain=[error])
    with pytest.raises(type(error)):
        await _call(client, rows, "auto:haiku")
    assert len(client.messages.calls) == 1 and not mc.is_failed("claude-haiku-5-5")
    assert _row_view(rows) == [("claude-haiku-5-5", "error", type(error).__name__)]


async def test_effort_goes_only_where_the_listing_says_it_is_supported(rows, monkeypatch):
    monkeypatch.setattr(settings, "claude_call_effort", "low")
    mc.install_snapshot([_entry("claude-sonnet-5", "sonnet", effort=True),
                         _entry("claude-haiku-4-5", "haiku", effort=False)], source="api")
    client = _client(plain=[_message(model="claude-sonnet-5"), _message(model="claude-haiku-4-5"),
                            _message(model="claude-x")])
    await _call(client, rows, "claude-sonnet-5")
    await _call(client, rows, "claude-haiku-4-5")
    await _call(client, rows, "claude-x")  # 목록에 없는 판 — 모르면 보내지 않는다 / unknown: not sent
    efforts = [call["output_config"].get("effort") for call in client.messages.calls]
    assert efforts == ["low", None, None]
    assert all(call["output_config"]["format"]["type"] == "json_schema" for call in client.messages.calls)


async def test_any_call_failure_is_recorded_and_raised(rows):
    # 우리 쪽 오류(벤더 예외가 아닌 것)도 그 호출의 비용 행 하나를 남기고 그대로 올린다 — 호출부가 예전에 하던 대로.
    # Our own errors (not vendor exceptions) also leave that call's one cost row and propagate, as callers did.
    client = _client(plain=[RuntimeError("boom")])
    with pytest.raises(RuntimeError):
        await _call(client, rows, "claude-sonnet-5")
    assert _row_view(rows) == [("claude-sonnet-5", "error", "RuntimeError")]
