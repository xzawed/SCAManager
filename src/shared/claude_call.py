"""공용 Claude JSON 호출 — 판 해석 · effort · 서버 대체 · 안전 거절 · Haiku→Sonnet · 새 판 거부 대체 (Issue #1905 ①b).

Shared Claude JSON call: resolution, effort, server fallback, refusals, Haiku-to-Sonnet and rejection fallback.

비용 행 — 앞선 시도(거절 · 거부 · 오류)는 이 도우미가 적고, 마지막 응답의 행은 호출부가 파싱을 마친 뒤
`record_response` 로 적는다(«파싱이 끝난 뒤에만 success» 규칙을 호출부가 그대로 지킨다).
Cost rows: this helper writes the earlier attempts (refusals, rejections, errors); the caller writes the final
response's rows with `record_response` after parsing, so "success only after parsing" stays the caller's rule.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import anthropic

from src.config import settings
from src.shared import model_catalog as mc
from src.shared.claude_metrics import extract_anthropic_usage

logger = logging.getLogger(__name__)

SERVER_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# 서버 대체가 없는 Haiku 의 거절은 검증된 최신 Sonnet 으로 다시(사용자 11-21 «Haiku는 Sonnet으로 대체 수행»).
# A Haiku refusal (no server fallback) is retried on the verified latest Sonnet (user decision 11-21).
_REFUSAL_RETRY_FROM = "haiku"
_REFUSAL_RETRY_TO = "sonnet"

# await record(model=, duration_ms=, status=, error_type=, input_tokens=, output_tokens=,
#              cache_read_tokens=, cache_creation_tokens=) — 호출부가 비용 행 하나를 쓴다 / the caller writes one row
CostRecorder = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class CallOutcome:
    """마지막 응답과 그 판 — refused 는 사슬 전체가 거절했다는 뜻 / the final response; refused = the whole chain refused."""

    response: object
    model: str              # 답한 판(서버 대체가 답했으면 그 판) / the model that answered
    requested: str          # 마지막에 부른 판 — 비용 행의 기준 / the model last called; cost rows key on it
    refused: bool
    fallback_served: bool
    started: float


def _refused(response) -> bool:
    return getattr(response, "stop_reason", None) == "refusal"


def _fallback_served(response) -> bool:
    iterations = getattr(getattr(response, "usage", None), "iterations", None)
    return isinstance(iterations, list) and any(getattr(i, "type", None) == "fallback_message" for i in iterations)


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


async def record_response(record: CostRecorder, response, *, model: str, duration_ms: float, status: str,
                          error_type: str = "") -> None:
    """응답 하나의 비용 행 — 서버 대체가 돌았으면 hop 마다(그 판 · 그 토큰), 아니면 한 행.

    Cost rows for one response: one per hop when a server fallback ran (each hop's model and tokens), else one.
    `model` 은 부른 판이다 — hop 의 model 이 비어 있으면 그 판이다 / `model` is the model called (hops without a model).
    앞 hop 은 거절한 판이다 — status 는 refused, 걸린 시간은 마지막 hop 에 둔다.
    Earlier hops are models that declined (status refused); the elapsed time goes on the last hop.
    """
    usage = getattr(response, "usage", None)
    iterations = getattr(usage, "iterations", None)
    hops = ([i for i in iterations if getattr(i, "type", None) in ("message", "fallback_message")]
            if isinstance(iterations, list) else [])
    if hops:
        for n, hop in enumerate(hops):
            last = n == len(hops) - 1
            await record(
                model=getattr(hop, "model", None) or model, duration_ms=duration_ms if last else 0.0,
                status=status if last else "refused", error_type=error_type if last else "",
                input_tokens=_int(getattr(hop, "input_tokens", 0)),
                output_tokens=_int(getattr(hop, "output_tokens", 0)),
                cache_read_tokens=_int(getattr(hop, "cache_read_input_tokens", 0)),
                cache_creation_tokens=_int(getattr(hop, "cache_creation_input_tokens", 0)),
            )
        return
    input_tokens, output_tokens = extract_anthropic_usage(response)
    await record(
        model=model, duration_ms=duration_ms, status=status, error_type=error_type,
        input_tokens=input_tokens, output_tokens=output_tokens,
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        cache_creation_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
    )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


async def _record_failure(record: CostRecorder, model: str, error_type: str, duration_ms: float) -> None:
    await record(model=model, duration_ms=duration_ms, status="error", error_type=error_type,
                 input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0)


@dataclass
class Unfinished:
    """취소(기한 · 바깥 취소)로 끝나 아직 비용 행이 없는 시도 — 호출부가 `flush` 로 자기 라벨을 붙여 적는다.

    Attempts that ended by cancellation (a deadline or an outer cancel) and have no cost row yet; the caller
    writes them with `flush` and its own label. 예외로 끝난 시도는 도우미가 이미 적었다 / exceptions are written.
    """

    out: tuple[str, float] | None = None          # 나가 있던 호출 (판, 시작 시각) / the call that was out
    held: tuple[str, float, str] | None = None    # 다음 시도를 기다리던 앞 실패 (판, ms, 임시 라벨) / held failure

    async def flush(self, record: CostRecorder, *, error_type: str) -> None:
        """남은 시도를 적고 비운다 — 두 번 불러도 한 번만 적힌다 / write what is left, once."""
        held, out = self.held, self.out
        self.held = self.out = None
        if held is not None:
            await _record_failure(record, held[0], held[2], held[1])
        if out is not None:
            await _record_failure(record, out[0], error_type, _elapsed_ms(out[1]))


class _Attempts:
    """한 번의 create_json_message 안의 시도들 — 예외로 끝나면 바로 적고, 취소로 끝나면 `Unfinished` 에 남는다.

    The attempts of one create_json_message run: written at once when they raise, left in `Unfinished` on cancel.
    """

    def __init__(self, client, record: CostRecorder, trace: Unfinished, request: dict) -> None:
        self.record = record
        self._client, self._trace, self._request = client, trace, request

    async def send(self, model: str):
        self._trace.out = (model, time.perf_counter())
        response = await send_once(self._client, model, **self._request)
        started = self._take_out()[1]
        return response, started

    def _take_out(self) -> tuple[str, float]:
        out, self._trace.out = self._trace.out, None
        return out  # type: ignore[return-value]  # send 가 늘 채운 뒤에만 부른다 / only after send set it

    async def fail(self, error_type: str) -> None:
        model, started = self._take_out()
        await _record_failure(self.record, model, error_type, _elapsed_ms(started))

    def hold(self, error_type: str) -> None:
        """다음 시도 결과에 따라 라벨이 정해지는 실패 — 걸린 시간은 지금 잰다 / label decided by the next attempt."""
        model, started = self._take_out()
        self._trace.held = (model, _elapsed_ms(started), error_type)

    async def release(self, error_type: str | None = None) -> None:
        held, self._trace.held = self._trace.held, None
        model, duration_ms, held_type = held  # type: ignore[misc]  # hold 뒤에만 부른다 / only after hold
        await _record_failure(self.record, model, error_type or held_type, duration_ms)


async def send_once(client, model: str, *, max_tokens: int, system: list, schema: dict, messages: list,
                    entry: mc.ModelEntry | None = None):
    """한 번 부른다 — effort 와 서버 대체는 목록이 그 판에 허락한 것만(모르면 보내지 않는다). 시험 호출도 이 꼴이다.

    One call; effort and server fallback only where the listing says the model takes them (unknown: not sent).
    The catalog probe uses this same shape. `entry` overrides the listing lookup (the probe passes its candidate).
    """
    entry = entry if entry is not None else mc.entry_for(model)
    output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
    if entry is not None and entry.supports_effort:
        output_config["effort"] = settings.claude_call_effort
    if entry is not None and entry.server_fallback:
        return await client.beta.messages.create(
            model=model, max_tokens=max_tokens, system=system, output_config=output_config, messages=messages,
            betas=[SERVER_FALLBACK_BETA], fallbacks="default",
        )
    return await client.messages.create(
        model=model, max_tokens=max_tokens, system=system, output_config=output_config, messages=messages,
    )


def _follows_a_line(model_value: str | None, default_value: str) -> bool:
    try:
        choice = mc.parse_model_value(model_value)
    except ValueError:
        choice = mc.ModelChoice("default")
    if choice.kind == "default":
        choice = mc.parse_model_value(default_value)
    return choice.kind == "auto"


def _previous_for(model: str) -> str | None:
    """새 판이 거부했을 때 다시 부를 판 — 그 계열의 바로 앞 검증판, 없으면 계열 기본판(같은 판이면 없음).

    The model to retry after a rejection: the line's previous verified model, else its fallback default.
    """
    line = mc.line_of(model)
    if line not in mc.KNOWN_LINES:
        return None
    previous = mc.previous_verified(line) or mc.FALLBACK_DEFAULT_BY_LINE[line]
    return None if previous == model else previous


async def _after_rejection(attempts: _Attempts, model: str, exc: anthropic.BadRequestError, *,
                           follows: bool):
    """새 판(auto)이 400 이면 바로 앞 판에 한 번 더 — 그 판이 답할 때만 새 판을 실패로 적는다.

    An auto-resolved model that 400s is retried once on the previous one; only if that answers is it failed.
    """
    previous = _previous_for(model) if follows else None
    if previous is None:
        await attempts.fail(type(exc).__name__)
        raise exc
    attempts.hold(type(exc).__name__)
    try:
        response, started = await attempts.send(previous)
    except Exception as retry_exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # 앞 판도 실패 = 판 탓이 아니다(지출 한도 같은 계정 쪽) — 표식 없이 첫 오류를 올린다.
        # The previous model failed too: not the model's fault (e.g. a spend limit); raise the first error.
        await attempts.release()
        await attempts.fail(type(retry_exc).__name__)
        raise exc from retry_exc
    await attempts.release(mc.MODEL_REJECTED)
    mc.mark_failed(model)
    logger.warning("claude model %s rejected the request and %s answered it — %s is marked failed",
                   model, previous, model)
    return previous, response, started


async def create_json_message(  # pylint: disable=too-many-arguments,too-many-locals  # 호출 꼴 그대로 / the request's shape
        client, *, model_value: str | None, default_value: str, max_tokens: int,
                              system: list, schema: dict, messages: list, record: CostRecorder,
                              unfinished: Unfinished | None = None) -> CallOutcome:
    """저장값으로 판을 정해 JSON 응답 하나를 받는다 — 처리하지 않는 예외는 그대로 올린다(호출부의 오류 분류 유지).

    Resolve the stored value and get one JSON response; unhandled exceptions propagate (callers keep classifying).
    - `auto` 판(검증된 최신)이 400 이면 바로 앞 판에 한 번 더 — 그 판이 답하면 새 판을 실패로 적는다(model_rejected).
      An auto-resolved model that 400s is retried once on the previous model; if that answers, the new one is failed.
    - Haiku 의 거절은 검증된 최신 Sonnet 으로 다시 · 서버 대체는 목록이 허락한 판에만.
      A Haiku refusal is retried on the verified latest Sonnet; server fallback only where the listing allows it.
    - 비용 행: 예외 · 거절로 끝난 시도는 여기서, 취소로 끝난 시도는 `unfinished` 에, 마지막 응답은 호출부가.
      Cost rows: raised or refused attempts here, cancelled ones in `unfinished`, the final response by the caller.
    """
    attempts = _Attempts(client, record, unfinished if unfinished is not None else Unfinished(),
                         {"max_tokens": max_tokens, "system": system, "schema": schema, "messages": messages})
    model = mc.resolve_model(model_value, default_value=default_value)
    try:
        response, started = await attempts.send(model)
    except anthropic.BadRequestError as exc:
        model, response, started = await _after_rejection(
            attempts, model, exc, follows=_follows_a_line(model_value, default_value))
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        # 벤더 예외가 아니어도 그 호출의 비용 행 하나를 남긴다(취소는 BaseException 이라 여기 오지 않는다).
        # Any failure leaves that call's cost row; cancellation is a BaseException and never lands here.
        await attempts.fail(type(exc).__name__)
        raise
    if _refused(response) and mc.line_of(model) == _REFUSAL_RETRY_FROM:
        await record_response(record, response, model=model, duration_ms=_elapsed_ms(started), status="refused")
        refused_on = model
        model = mc.verified_latest(_REFUSAL_RETRY_TO) or mc.FALLBACK_DEFAULT_BY_LINE[_REFUSAL_RETRY_TO]
        logger.info("claude refusal on %s — retrying on %s", refused_on, model)
        try:
            response, started = await attempts.send(model)
        except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
            await attempts.fail(type(exc).__name__)
            raise
    if _refused(response):
        stop_details = getattr(response, "stop_details", None)
        logger.warning("claude refusal (whole chain) on %s — category=%s", model,
                       getattr(stop_details, "category", None))
    # 응답의 model 은 날짜 붙은 id 일 수 있다 — 서버 대체가 답했을 때만 그쪽을 쓴다.
    # The response may echo a dated id; take it only when a server fallback answered.
    fallback = _fallback_served(response)
    served = getattr(response, "model", None)
    answered = served if fallback and isinstance(served, str) and served else model
    return CallOutcome(response=response, model=answered, requested=model, refused=_refused(response),
                       fallback_served=fallback, started=started)
