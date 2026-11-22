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


async def _record_failure(record: CostRecorder, model: str, error_type: str, started: float) -> None:
    await record(model=model, duration_ms=(time.perf_counter() - started) * 1000.0, status="error",
                 error_type=error_type, input_tokens=0, output_tokens=0, cache_read_tokens=0, cache_creation_tokens=0)


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


async def create_json_message(client, *, model_value: str | None, default_value: str, max_tokens: int,
                              system: list, schema: dict, messages: list, record: CostRecorder) -> CallOutcome:
    """저장값으로 판을 정해 JSON 응답 하나를 받는다 — 처리하지 않는 예외는 그대로 올린다(호출부의 오류 분류 유지).

    Resolve the stored value and get one JSON response; unhandled exceptions propagate (callers keep classifying).
    - `auto` 판(검증된 최신)이 400 이면 바로 앞 판에 한 번 더 — 그 판이 답하면 새 판을 실패로 적는다(model_rejected).
      An auto-resolved model that 400s is retried once on the previous model; if that answers, the new one is failed.
    - Haiku 의 거절은 검증된 최신 Sonnet 으로 다시 · 서버 대체는 목록이 허락한 판에만.
      A Haiku refusal is retried on the verified latest Sonnet; server fallback only where the listing allows it.
    """
    model = mc.resolve_model(model_value, default_value=default_value)
    started = time.perf_counter()
    try:
        response = await send_once(client, model, max_tokens=max_tokens, system=system, schema=schema,
                                   messages=messages)
    except anthropic.BadRequestError as exc:
        previous = _previous_for(model) if _follows_a_line(model_value, default_value) else None
        if previous is None:
            await _record_failure(record, model, type(exc).__name__, started)
            raise
        retry_started = time.perf_counter()
        try:
            response = await send_once(client, previous, max_tokens=max_tokens, system=system, schema=schema,
                                       messages=messages)
        except anthropic.APIError as retry_exc:
            # 앞 판도 실패 = 판 탓이 아니다(지출 한도 같은 계정 쪽) — 표식 없이 첫 오류를 올린다.
            # The previous model failed too: not the model's fault (e.g. a spend limit); raise the first error.
            await _record_failure(record, model, type(exc).__name__, started)
            await _record_failure(record, previous, type(retry_exc).__name__, retry_started)
            raise exc from retry_exc
        await _record_failure(record, model, mc.MODEL_REJECTED, started)
        mc.mark_failed(model)
        logger.warning("claude model %s rejected the request and %s answered it — %s is marked failed",
                       model, previous, model)
        model, started = previous, retry_started
    except anthropic.APIError as exc:
        await _record_failure(record, model, type(exc).__name__, started)
        raise
    if _refused(response) and mc.line_of(model) == _REFUSAL_RETRY_FROM:
        await record_response(record, response, model=model,
                              duration_ms=(time.perf_counter() - started) * 1000.0, status="refused")
        target = mc.verified_latest(_REFUSAL_RETRY_TO) or mc.FALLBACK_DEFAULT_BY_LINE[_REFUSAL_RETRY_TO]
        logger.info("claude refusal on %s — retrying on %s", model, target)
        started = time.perf_counter()
        try:
            response = await send_once(client, target, max_tokens=max_tokens, system=system, schema=schema,
                                       messages=messages)
        except anthropic.APIError as exc:
            await _record_failure(record, target, type(exc).__name__, started)
            raise
        model = target
    served = getattr(response, "model", None)
    if _refused(response):
        stop_details = getattr(response, "stop_details", None)
        logger.warning("claude refusal (whole chain) on %s — category=%s", model,
                       getattr(stop_details, "category", None))
    return CallOutcome(response=response, model=served if isinstance(served, str) and served else model,
                       requested=model, refused=_refused(response), fallback_served=_fallback_served(response),
                       started=started)
