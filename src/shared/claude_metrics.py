"""Claude API 호출 메트릭 — 비용 추정 + 구조화 로깅.

Phase E.2b — Claude API cost/latency/token 추적 기반.

Anthropic API 가격 정책 (USD per 1M tokens, **2026-04 기준**):
  - Opus : $15 input / $75 output
  - Sonnet: $3 input / $15 output  ← 기본값 (claude-sonnet-4-6 등)
  - Haiku : $1 input / $5 output

⚠️ **정확도 경고**:
  - 가격은 Anthropic 측 변경 가능 — **분기별 (3개월) 재확인 필수**.
  - 추세 추적용 추정이므로 실제 청구 대비 ±10% 오차 허용.
  - 월별 실제 청구액 vs 본 모듈 합계 차이 10% 초과 시 즉시 가격표 갱신.
  - 미지의 모델 이름은 sonnet 요율로 fallback — typo 시 과소/과대 추정 가능.
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

# Anthropic prompt caching 가격 정책 (input rate 기준 배수)
# Anthropic prompt caching pricing (multiplier on input rate)
_CACHE_READ_MULTIPLIER = 0.1   # 캐시 읽기 = input 정가의 1/10
_CACHE_CREATION_MULTIPLIER = 1.25  # 캐시 생성 = input 정가의 1.25× (5분 TTL 회수)

# silent fallback 차단 — 5회 연속 cache_creation>0 + cache_read=0 시 WARNING
# Silent-fallback guard — WARN after 5 consecutive creation>0 + read==0 calls.
_SILENT_FALLBACK_THRESHOLD = 5


def estimate_claude_cost_usd(
    *,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> float:
    """모델 + 토큰 수로 USD 비용 추정 (cache 비용 모델 포함). 정확도 ±10% 허용.

    Estimate USD cost from model + token counts (includes cache pricing). ±10% tolerance.

    cache_read = input rate × 0.1 (10× cheaper) / cache_creation = input rate × 1.25.
    """
    model_lower = (model or "").lower()
    family = _DEFAULT_FAMILY
    for key in _PRICING_USD_PER_MTOK:
        if key in model_lower:
            family = key
            break
    in_rate, out_rate = _PRICING_USD_PER_MTOK[family]
    return (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * in_rate * _CACHE_READ_MULTIPLIER
        + cache_creation_tokens * in_rate * _CACHE_CREATION_MULTIPLIER
    ) / 1_000_000


# 메모리 카운터 — 운영 cache hit rate 추세 추적 (process 재시작 시 reset)
# In-memory counters — track cache hit-rate trend (reset on process restart).
_cache_stats: dict[str, int | float] = {
    "total_calls": 0,
    "cache_read_tokens": 0,
    "cache_creation_tokens": 0,
    "input_tokens": 0,
}
_silent_fallback_streak: int = 0  # 연속 creation>0 + read==0 카운터


def reset_cache_stats() -> None:
    """카운터 초기화 — 테스트 격리 + 운영 수동 리셋용.

    Reset counters — for test isolation and operational manual reset.
    """
    global _silent_fallback_streak  # pylint: disable=global-statement
    _cache_stats.update(
        total_calls=0, cache_read_tokens=0, cache_creation_tokens=0, input_tokens=0,
    )
    _silent_fallback_streak = 0


def get_cache_stats() -> dict[str, int | float]:
    """현재 누적 cache 통계 + hit_rate 반환 (process 시작 이후 누적).

    Return cumulative cache stats + hit_rate since process start.
    cache_hit_rate = cache_read / (cache_read + input).
    """
    read = _cache_stats["cache_read_tokens"]
    inp = _cache_stats["input_tokens"]
    denom = read + inp
    hit_rate = (read / denom) if denom > 0 else 0.0
    return {**_cache_stats, "cache_hit_rate": hit_rate}


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
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
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
        cache_read_tokens: prompt cache 에서 읽은 토큰 수 (기본 0).
            Anthropic 정가 대비 1/10 비용으로 청구됨.
            Cached tokens read from prompt cache (10× cheaper than fresh input).
        cache_creation_tokens: prompt cache 생성 토큰 수 (기본 0).
            정가 대비 1.25× 비용 (캐시 등록 비용 — 5분 TTL 내 재사용 시 절감 회수).
            Tokens written to prompt cache (1.25× normal cost; recouped on hits).
    """
    # defensive — 호출자 (특히 mock 테스트) 가 비-int 전달 시 0 으로 정규화
    # Defensive coercion — callers (esp. mocks) may pass non-int; normalize to 0.
    try:
        cache_read_tokens = int(cache_read_tokens or 0)
        cache_creation_tokens = int(cache_creation_tokens or 0)
    except (TypeError, ValueError):
        cache_read_tokens, cache_creation_tokens = 0, 0
    cost_usd = estimate_claude_cost_usd(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_creation_tokens=cache_creation_tokens,
    )
    # 누적 카운터 갱신 — silent fallback 차단 streak 추적 페어
    # Update cumulative counters — pairs with silent-fallback streak guard.
    global _silent_fallback_streak  # pylint: disable=global-statement
    _cache_stats["total_calls"] += 1
    _cache_stats["cache_read_tokens"] += cache_read_tokens
    _cache_stats["cache_creation_tokens"] += cache_creation_tokens
    _cache_stats["input_tokens"] += input_tokens
    if status == "success":
        if cache_creation_tokens > 0 and cache_read_tokens == 0:
            _silent_fallback_streak += 1
        else:
            _silent_fallback_streak = 0
    extra = {
        "claude_model": model,
        "duration_ms": duration_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost_usd,
        "status": status,
        "cache_read_tokens": cache_read_tokens,
        "cache_creation_tokens": cache_creation_tokens,
    }
    if error_type:
        extra["error_type"] = error_type

    if status == "success":
        logger.info(
            "claude_api_call model=%s duration_ms=%.0f input_tokens=%d output_tokens=%d "
            "cache_read=%d cache_creation=%d cost_usd=%.4f status=%s",
            model, duration_ms, input_tokens, output_tokens,
            cache_read_tokens, cache_creation_tokens, cost_usd, status,
            extra=extra,
        )
        # silent fallback 의심 — caching 등록만 발생 + 읽기 0 → cache 미작동
        # Suspect silent fallback — only cache writes, no reads → caching inactive.
        if _silent_fallback_streak >= _SILENT_FALLBACK_THRESHOLD:
            logger.warning(
                "claude_api_call silent_cache_fallback streak=%d "
                "(cache_creation>0 + cache_read=0 N회 연속 — system_text 1024 토큰 미달 가능)",
                _silent_fallback_streak,
            )
            _silent_fallback_streak = 0  # 재 alert 방지
    else:
        logger.warning(
            "claude_api_call model=%s duration_ms=%.0f status=%s error_type=%s",
            model, duration_ms, status, error_type,
            extra=extra,
        )
