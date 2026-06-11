"""OpenAI API 호출 메트릭 — 비용 추정 + 구조화 로깅 (검증자용, claude_metrics 대칭).
OpenAI API call metrics — cost estimate + structured logging (for the verifier).

⚠️ 가격은 OpenAI 측 변경 가능 — 분기별 재확인 필수. 미지 모델은 default 요율 fallback.
⚠️ Prices may change on OpenAI's side — verify quarterly. Unknown models fall back to default rate.
"""
import inspect
import logging

logger = logging.getLogger(__name__)

# 모델 패밀리별 가격 (USD per 1M tokens, input/output) — 구현 시 최신 단가로 확정
# Per-model-family pricing (USD per 1M tokens, input/output) — confirm latest rates at implementation time
_PRICING_USD_PER_MTOK = {
    "mini": (0.15, 0.60),   # 저가 소형 (예시 단가 — 구현 시 확정)
    # Low-cost compact model (example rate — confirm at implementation)
}
_DEFAULT_RATE = (0.15, 0.60)  # 미지 모델 → 소형 요율로 보수적 추정
# Unknown model → conservative estimate using compact model rate


async def aclose_openai_client(client) -> None:
    """호출당 생성한 AsyncOpenAI(httpx 풀)를 안전 종료 — awaitable 일 때만 await.
    Close a per-call AsyncOpenAI httpx pool; await only when awaitable (real SDK), skip test doubles.
    (claude_metrics.aclose_anthropic_client 미러 — 정책 16 >=2 사용처)
    """
    closer = getattr(client, "aclose", None)
    if closer is None:
        return
    result = closer()
    if inspect.isawaitable(result):
        await result


def estimate_openai_cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float:
    """모델 + 토큰 수로 USD 비용 추정. 정확도 +-10% 허용.
    Estimate USD cost from model name + token counts. Accuracy tolerance +-10%.
    """
    model_lower = (model or "").lower()
    in_rate, out_rate = _DEFAULT_RATE
    for key, rate in _PRICING_USD_PER_MTOK.items():
        if key in model_lower:
            in_rate, out_rate = rate
            break
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def extract_openai_usage(response: object) -> tuple[int, int]:
    """OpenAI 응답에서 (input_tokens, output_tokens) 추출. usage 누락 시 (0, 0).
    Extract (input_tokens, output_tokens) from an OpenAI response. Returns (0, 0) if usage is absent.
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    in_tok = getattr(usage, "prompt_tokens", 0) or 0
    out_tok = getattr(usage, "completion_tokens", 0) or 0
    return int(in_tok), int(out_tok)


def log_openai_api_call(
    *, model: str, duration_ms: float, input_tokens: int, output_tokens: int,
    status: str, error_type: str = "",
) -> None:
    """OpenAI 검증 호출 1건의 구조화 메트릭 로그 (LogRecord extra).
    Emit a structured metric log entry for a single OpenAI verifier call (LogRecord extra).
    """
    cost_usd = estimate_openai_cost_usd(
        model=model, input_tokens=input_tokens, output_tokens=output_tokens)
    extra = {
        "openai_model": model, "duration_ms": duration_ms,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "cost_usd": cost_usd, "status": status,
    }
    if error_type:
        extra["error_type"] = error_type
    if status == "success":
        logger.info(
            "openai_verifier_call model=%s duration_ms=%.0f input_tokens=%d "
            "output_tokens=%d cost_usd=%.4f status=%s",
            model, duration_ms, input_tokens, output_tokens, cost_usd, status, extra=extra,
        )
    else:
        logger.warning(
            "openai_verifier_call model=%s duration_ms=%.0f status=%s error_type=%s",
            model, duration_ms, status, error_type, extra=extra,
        )
