"""Claude API 호출 메트릭 — 비용 추정 + 구조화 로깅.

Phase E.2b — Claude API cost/latency/token 추적 기반.
Anthropic API 가격 정책 (USD per 1M tokens):
  - Opus : $15 input / $75 output
  - Sonnet: $3 input / $15 output  ← 기본값 (claude-sonnet-4-6 등)
  - Haiku : $1 input / $5 output
정확한 가격은 주기적 재확인 필요 — 추세 추적용 추정이므로 ±10% 오차 허용.
"""
import logging

logger = logging.getLogger(__name__)

# 모델 패밀리별 가격 (USD per 1M tokens, input/output)
_PRICING_USD_PER_MTOK = {
    "opus": (15.0, 75.0),
    "sonnet": (3.0, 15.0),
    "haiku": (1.0, 5.0),
}
_DEFAULT_FAMILY = "sonnet"  # 미지 모델 → sonnet 가격으로 보수적 추정


def estimate_claude_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """모델 + 토큰 수로 USD 비용 추정. 정확도 ±10% 허용 (추세 추적용)."""
    model_lower = (model or "").lower()
    family = _DEFAULT_FAMILY
    for key in _PRICING_USD_PER_MTOK:
        if key in model_lower:
            family = key
            break
    in_rate, out_rate = _PRICING_USD_PER_MTOK[family]
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def extract_anthropic_usage(response: object) -> tuple[int, int]:
    """anthropic Response 객체에서 (input_tokens, output_tokens) 추출.

    `response.usage` 가 없거나 속성 누락 시 (0, 0) 반환 (stream/에러 응답 등).
    """
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    input_tok = getattr(usage, "input_tokens", 0) or 0
    output_tok = getattr(usage, "output_tokens", 0) or 0
    return int(input_tok), int(output_tok)


def log_claude_api_call(
    *,
    model: str,
    duration_ms: float,
    input_tokens: int,
    output_tokens: int,
    status: str,
    error_type: str = "",
) -> None:
    """Claude API 호출 1건의 구조화된 메트릭 로그.

    LogRecord extra 로 필드를 첨부해 structured log shipper (Sentry, CloudWatch 등)
    가 파싱할 수 있도록 한다.

    Args:
        model: 호출된 모델 ID (예: "claude-sonnet-4-6")
        duration_ms: API 호출 전체 소요 시간 (ms)
        input_tokens / output_tokens: 입력/출력 토큰 수 (에러 시 0)
        status: "success" | "error" | "timeout"
        error_type: 에러 타입 이름 (status=="error" 일 때)
    """
    cost_usd = estimate_claude_cost_usd(
        model=model, input_tokens=input_tokens, output_tokens=output_tokens,
    )
    extra = {
        "claude_model": model,
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "status": status,
    }
    if error_type:
        extra["error_type"] = error_type

    if status == "success":
        logger.info(
            "claude_api_call model=%s duration_ms=%.0f input_tokens=%d output_tokens=%d "
            "cost_usd=%.4f status=%s",
            model, duration_ms, input_tokens, output_tokens, cost_usd, status,
            extra=extra,
        )
    else:
        logger.warning(
            "claude_api_call model=%s duration_ms=%.0f status=%s error_type=%s",
            model, duration_ms, status, error_type,
            extra=extra,
        )
