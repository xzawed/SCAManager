"""공용 Claude 호출 도우미 — 판 해석 · effort · 서버 대체 · 안전 거절 · Haiku→Sonnet · 새 판 거부 대체 (Issue #1905 ①b).

The shared Claude call helper: resolution, effort, server fallback, refusals, Haiku-to-Sonnet and rejection fallback.
가짜는 바깥 경계(Anthropic 클라이언트 · 비용 행 기록)에만 둔다 — 응답은 SDK 의 실제 타입으로 만든다.
Fakes sit only at the outer boundaries; responses are built from the SDK's real types.
"""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import anthropic
import httpx
import pytest
from anthropic.types import Message
from anthropic.types.beta import BetaMessage

from src.shared import claude_call as cc
from src.shared import model_catalog as mc

_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
_SYSTEM = [{"type": "text", "text": "Reply with JSON."}]
_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
_MESSAGES = [{"role": "user", "content": "x"}]


def _d(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _entry(model_id: str, line: str, *, effort: bool = True, server_fallback: bool | None = None,
           created: datetime | None = None, levels: frozenset | None = None) -> mc.ModelEntry:
    if levels is None:
        levels = frozenset({"low", "medium", "high"}) if effort else frozenset()
    return mc.ModelEntry(id=model_id, line=line, display_name=model_id, created_at=created or _d(2026, 10, 1),
                         deprecated_at=None, retires_at=None, supports_structured_outputs=True,
                         supports_effort=effort, server_fallback=server_fallback, effort_levels=levels)


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


_HANG = object()  # 응답이 오지 않는 호출 — 기한 · 바깥 취소로만 끝난다 / a call that never answers


class _FakeCreate:
    def __init__(self, outcomes):
        self.calls = []
        self._outcomes = list(outcomes)

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if outcome is _HANG:
            await asyncio.Event().wait()
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


async def _call(client, rows, value, *, default="claude-sonnet-5", unfinished=None, effort=None):
    return await cc.create_json_message(client, model_value=value, default_value=default, max_tokens=256,
                                        system=_SYSTEM, schema=_SCHEMA, messages=_MESSAGES, record=rows.record,
                                        unfinished=unfinished, effort=effort)


async def _cancel_while_hanging(client, rows, value, unfinished, *, hung_calls: int):
    task = asyncio.ensure_future(_call(client, rows, value, unfinished=unfinished))
    while len(client.messages.calls) + len(client.beta.messages.calls) < hung_calls:
        await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


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


async def test_effort_goes_only_where_the_listing_says_it_is_supported(rows):
    mc.install_snapshot([_entry("claude-sonnet-5", "sonnet", effort=True),
                         _entry("claude-haiku-4-5", "haiku", effort=False)], source="api")
    client = _client(plain=[_message(model="claude-sonnet-5"), _message(model="claude-haiku-4-5"),
                            _message(model="claude-x")])
    await _call(client, rows, "claude-sonnet-5", effort="low")
    await _call(client, rows, "claude-haiku-4-5", effort="low")
    await _call(client, rows, "claude-x", effort="low")  # 목록에 없는 판 — 모르면 보내지 않는다 / unknown: not sent
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


async def test_answered_model_stays_the_called_id_without_a_fallback(rows):
    # 응답의 model 은 날짜 붙은 id 일 수 있다 — 서버 대체가 답한 때만 응답 쪽을 믿는다.
    # The response may echo a dated id; only a server-fallback answer takes the response's model.
    client = _client(plain=[_message(model="claude-sonnet-5-20260401")])
    outcome = await _call(client, rows, "claude-sonnet-5")
    assert (outcome.model, outcome.requested) == ("claude-sonnet-5", "claude-sonnet-5")


async def test_cancelled_call_is_left_for_the_caller_to_label(rows):
    # 기한 · 바깥 취소는 도우미가 적지 않는다 — 호출부가 자기 라벨(TimeoutError 등)로 적는다.
    # Cancellation is not written by the helper; the caller writes it with its own label (e.g. TimeoutError).
    unfinished = cc.Unfinished()
    await _cancel_while_hanging(_client(plain=[_HANG]), rows, "claude-sonnet-5", unfinished, hung_calls=1)
    assert rows.rows == []
    await unfinished.flush(rows.record, error_type="TimeoutError")
    assert _row_view(rows) == [("claude-sonnet-5", "error", "TimeoutError")]
    await unfinished.flush(rows.record, error_type="TimeoutError")
    assert len(rows.rows) == 1  # 두 번 적지 않는다 / never twice


async def test_cancel_during_the_rejection_retry_leaves_both_attempts(rows):
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    unfinished = cc.Unfinished()
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400), _HANG])
    await _cancel_while_hanging(client, rows, "auto:haiku", unfinished, hung_calls=2)
    await unfinished.flush(rows.record, error_type="CancelledError")
    # 앞 판이 답하지 못했으니 새 판 탓인지 모른다 — 실패 표식을 달지 않는다
    # The previous model never answered, so the new one is not blamed.
    assert _row_view(rows) == [("claude-haiku-5-5", "error", "BadRequestError"),
                               ("claude-haiku-4-5", "error", "CancelledError")]
    assert not mc.is_failed("claude-haiku-5-5")


async def test_cancel_during_the_refusal_retry_keeps_the_refused_row(rows):
    unfinished = cc.Unfinished()
    client = _client(plain=[_message(model="claude-haiku-4-5", stop_reason="refusal", text=None), _HANG])
    await _cancel_while_hanging(client, rows, "claude-haiku-4-5", unfinished, hung_calls=2)
    await unfinished.flush(rows.record, error_type="CancelledError")
    assert _row_view(rows) == [("claude-haiku-4-5", "refused", ""), ("claude-sonnet-5", "error", "CancelledError")]


async def test_finished_calls_leave_nothing_unfinished(rows):
    unfinished = cc.Unfinished()
    await _call(_client(plain=[_message(model="claude-sonnet-5")]), rows, "claude-sonnet-5", unfinished=unfinished)
    with pytest.raises(anthropic.RateLimitError):
        await _call(_client(plain=[_status_error(anthropic.RateLimitError, 429)]), rows, "claude-sonnet-5",
                    unfinished=unfinished)
    await unfinished.flush(rows.record, error_type="TimeoutError")
    assert _row_view(rows) == [("claude-sonnet-5", "error", "RateLimitError")]


async def test_failure_rows_carry_their_own_elapsed_time(rows):
    # 앞 실패의 걸린 시간은 그 호출의 것이다 — 뒤 재시도 시간이 섞이지 않는다
    # An earlier failure's duration is its own; the retry's time is not added to it.
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")

    class _SlowRetry(_FakeCreate):
        async def create(self, **kwargs):
            if self.calls:
                await asyncio.sleep(0.05)
            return await super().create(**kwargs)

    client = SimpleNamespace(messages=_SlowRetry([_status_error(anthropic.BadRequestError, 400),
                                                  _message(model="claude-haiku-4-5")]),
                             beta=SimpleNamespace(messages=_FakeCreate([])))
    await _call(client, rows, "auto:haiku")
    (rejected,) = rows.rows
    assert rejected["error_type"] == "model_rejected" and rejected["duration_ms"] < 40


async def test_unreadable_hop_tokens_count_as_zero(rows):
    response = SimpleNamespace(usage=SimpleNamespace(iterations=[
        SimpleNamespace(type="message", model="claude-sonnet-5-5", input_tokens="n/a", output_tokens=None,
                        cache_read_input_tokens=0, cache_creation_input_tokens=0)]))
    await cc.record_response(rows.record, response, model="claude-sonnet-5-5", duration_ms=1.0, status="success")
    assert (rows.rows[0]["input_tokens"], rows.rows[0]["output_tokens"]) == (0, 0)


async def test_unreadable_stored_value_follows_the_default_line(rows):
    # 읽을 수 없는 저장값은 기본값으로 — 기본값이 auto 면 새 판 거부 대체도 그대로 돈다
    # An unreadable stored value falls back to the default; an auto default keeps the rejection fallback.
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400), _message(model="claude-haiku-4-5")])
    outcome = await _call(client, rows, "auto:nonsense", default="auto:haiku")
    assert outcome.model == "claude-haiku-4-5" and mc.is_failed("claude-haiku-5-5")


async def test_auto_model_outside_the_known_lines_is_not_retried(rows):
    mc.set_verified("haiku", "custom-model")
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400)])
    with pytest.raises(anthropic.BadRequestError):
        await _call(client, rows, "auto:haiku")
    assert len(client.messages.calls) == 1
    assert _row_view(rows) == [("custom-model", "error", "BadRequestError")]


async def test_refusal_retry_failure_is_recorded_and_raised(rows):
    client = _client(plain=[_message(model="claude-haiku-4-5", stop_reason="refusal", text=None),
                            _status_error(anthropic.RateLimitError, 429)])
    with pytest.raises(anthropic.RateLimitError):
        await _call(client, rows, "claude-haiku-4-5")
    assert _row_view(rows) == [("claude-haiku-4-5", "refused", ""), ("claude-sonnet-5", "error", "RateLimitError")]


async def test_system_is_left_out_when_the_caller_has_none(rows):
    # 리포 인사이트는 system 없이 부른다 — None(요청 본문의 null)이 아니라 SDK 의 omit 을 넘긴다
    # The repo insight call has no system prompt: the SDK's omit, never None (a null in the request body).
    client = _client(plain=[_message(model="claude-haiku-4-5")])
    await cc.create_json_message(client, model_value="claude-haiku-4-5", default_value="claude-sonnet-5",
                                 max_tokens=64, system=None, schema=_SCHEMA, messages=_MESSAGES, record=rows.record)
    assert client.messages.calls[0].get("system", anthropic.omit) is anthropic.omit


async def _cancel_during_a_write(client, value, *, written, unfinished):
    """도우미 안의 비용 행 쓰기가 도는 중에 취소한다 — 기한이 쓰기 await 에 걸린 경우.
    Cancel while a cost-row write inside the helper is running: a deadline landing on that await.
    """
    writing = asyncio.Event()

    async def _slow_record(**row):
        writing.set()
        await asyncio.sleep(0.05)
        written.append((row["model"], row["status"], row["error_type"]))

    task = asyncio.ensure_future(cc.create_json_message(
        client, model_value=value, default_value="claude-sonnet-5", max_tokens=64, system=_SYSTEM,
        schema=_SCHEMA, messages=_MESSAGES, record=_slow_record, unfinished=unfinished))
    await writing.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0.1)  # 끝까지 도는 쓰기를 기다린다 / let the write run to its end
    await unfinished.flush(_slow_record, error_type="TimeoutError")


async def test_cancel_during_the_rejected_row_write_keeps_the_row_and_the_mark():
    # 앞 판이 답한 뒤 거부 행을 쓰는 중에 기한이 오면 — 행도 실패 표식도 남는다, 두 번 적히지 않는다
    # A deadline during the rejected-row write: the row and the failure mark both survive, written once.
    mc.set_verified("haiku", "claude-haiku-4-5")
    mc.set_verified("haiku", "claude-haiku-5-5")
    written = []
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400), _message(model="claude-haiku-4-5")])
    await _cancel_during_a_write(client, "auto:haiku", written=written, unfinished=cc.Unfinished())
    assert written == [("claude-haiku-5-5", "error", "model_rejected")]
    assert mc.is_failed("claude-haiku-5-5")


async def test_cancel_during_the_refused_row_write_keeps_that_row():
    written = []
    client = _client(plain=[_message(model="claude-haiku-4-5", stop_reason="refusal", text=None),
                            _message(model="claude-sonnet-5")])
    await _cancel_during_a_write(client, "claude-haiku-4-5", written=written, unfinished=cc.Unfinished())
    assert written == [("claude-haiku-4-5", "refused", "")]


async def test_rejected_fallback_arguments_are_dropped_for_the_process(rows):
    # 서버 대체 인자를 400 으로 거부한 판 — 그 시도 행 하나, 대체 없이 다시, 이 프로세스에선 다시 보내지 않는다
    # A model that 400s on the fallback arguments: one row, a plain retry, and no fallbacks again this process.
    mc.install_snapshot([_entry("claude-sonnet-5", "sonnet", server_fallback=True)], source="api")
    client = _client(beta=[_status_error(anthropic.BadRequestError, 400)],
                     plain=[_message(model="claude-sonnet-5"), _message(model="claude-sonnet-5")])
    first = await _call(client, rows, "claude-sonnet-5")
    second = await _call(client, rows, "claude-sonnet-5")
    assert (len(client.beta.messages.calls), len(client.messages.calls)) == (1, 2)
    assert _row_view(rows) == [("claude-sonnet-5", "error", "fallbacks_rejected")]
    assert (first.model, second.model, first.refused) == ("claude-sonnet-5", "claude-sonnet-5", False)


async def test_a_new_model_that_rejects_both_shapes_is_still_a_rejection(rows):
    mc.install_snapshot([_entry("claude-sonnet-5-5", "sonnet", server_fallback=True),
                         _entry("claude-sonnet-5", "sonnet", created=_d(2026, 4, 1))], source="api")
    mc.set_verified("sonnet", "claude-sonnet-5")
    mc.set_verified("sonnet", "claude-sonnet-5-5")
    client = _client(beta=[_status_error(anthropic.BadRequestError, 400)],
                     plain=[_status_error(anthropic.BadRequestError, 400), _message(model="claude-sonnet-5")])
    outcome = await _call(client, rows, "auto:sonnet")
    assert outcome.model == "claude-sonnet-5" and mc.is_failed("claude-sonnet-5-5")
    assert _row_view(rows) == [("claude-sonnet-5-5", "error", "fallbacks_rejected"),
                               ("claude-sonnet-5-5", "error", "model_rejected")]


async def test_a_model_already_failed_by_another_call_retries_on_the_latest_good_one(rows):
    # 같은 새 판에 두 호출이 동시에 400 — 먼저 끝난 쪽이 실패로 적으면 뒤쪽은 «남은 최신» 으로(그 앞까지 내려가지 않는다)
    # Two concurrent calls 400 on the same new model: once one marks it failed, the other retries on the latest good.
    for model_id in ("claude-haiku-3-5", "claude-haiku-4-5", "claude-haiku-5-5"):
        mc.set_verified("haiku", model_id)

    class _MarkedMeanwhile(_FakeCreate):
        async def create(self, **kwargs):
            if not self.calls:
                mc.mark_failed("claude-haiku-5-5")  # 다른 호출이 그 사이에 / another call, meanwhile
            return await super().create(**kwargs)

    client = SimpleNamespace(messages=_MarkedMeanwhile([_status_error(anthropic.BadRequestError, 400),
                                                        _message(model="claude-haiku-4-5")]),
                             beta=SimpleNamespace(messages=_FakeCreate([])))
    outcome = await _call(client, rows, "auto:haiku")
    assert [call["model"] for call in client.messages.calls] == ["claude-haiku-5-5", "claude-haiku-4-5"]
    assert outcome.model == "claude-haiku-4-5"


async def test_a_line_without_an_earlier_verified_model_retries_on_its_default(rows):
    mc.set_verified("haiku", "claude-haiku-5-5")
    client = _client(plain=[_status_error(anthropic.BadRequestError, 400), _message(model="claude-haiku-4-5")])
    outcome = await _call(client, rows, "auto:haiku")
    assert [call["model"] for call in client.messages.calls] == ["claude-haiku-5-5", "claude-haiku-4-5"]
    assert outcome.model == "claude-haiku-4-5" and mc.is_failed("claude-haiku-5-5")


def _hop(kind: str, model, tokens: int):
    return SimpleNamespace(type=kind, model=model, input_tokens=tokens, output_tokens=1,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0)


async def test_primary_hops_carry_the_called_id_and_fallback_hops_their_own(rows):
    # 부른 판의 hop 은 부른 id 그대로(응답이 날짜 id 를 줘도) · 대체 hop 만 그 판 이름 · 고정 대체(sticky)는 대체 hop 하나
    # A primary hop keeps the called id (even if a dated id is echoed); only fallback hops name their model.
    dated = SimpleNamespace(usage=SimpleNamespace(iterations=[
        _hop("message", "claude-sonnet-5-20260401", 9), _hop("fallback_message", "claude-opus-5", 12)]))
    sticky = SimpleNamespace(usage=SimpleNamespace(iterations=[_hop("fallback_message", "claude-opus-5", 7)]))
    await cc.record_response(rows.record, dated, model="claude-sonnet-5", duration_ms=5.0, status="success")
    await cc.record_response(rows.record, sticky, model="claude-sonnet-5", duration_ms=5.0, status="success")
    assert [(r["model"], r["status"], r["input_tokens"]) for r in rows.rows] == [
        ("claude-sonnet-5", "refused", 9), ("claude-opus-5", "success", 12), ("claude-opus-5", "success", 7)]


# witness-corpus: 요청 단계 — 판이 받는 단계 · 받지 않아 내려 맞출 단계 · 내려갈 곳이 없는 단계 · 모르는 값 · 비움
_EFFORT_REQUESTS = [
    ("high", frozenset({"low", "medium", "high"}), "high"),
    ("high", frozenset({"low", "medium"}), "medium"),
    ("medium", frozenset({"low"}), "low"),
    ("low", frozenset({"high", "max"}), None),
    ("max", frozenset({"low", "medium", "high"}), "high"),
    ("turbo", frozenset({"low", "medium", "high"}), None),
    (None, frozenset({"low", "medium", "high"}), None),
]


@pytest.mark.parametrize(("requested", "levels", "sent"), _EFFORT_REQUESTS)
async def test_the_requested_effort_is_fitted_to_what_the_model_takes(rows, requested, levels, sent):
    # 받으면 그 단계 · 아니면 받는 가장 가까운 아래 단계 · 없거나 요청이 비면 보내지 않는다(판의 기본값)
    # The level if taken, else the nearest lower level taken; nothing when none fits or none was asked.
    mc.install_snapshot([_entry("claude-sonnet-5", "sonnet", levels=levels)], source="api")
    client = _client(plain=[_message(model="claude-sonnet-5")])
    await _call(client, rows, "claude-sonnet-5", effort=requested)
    assert client.messages.calls[0]["output_config"].get("effort") == sent
