"""Claude API 호출 메트릭 — 비용 추정 + 구조화 로깅.

Phase E.2b — Claude API cost/latency/token 추적 기반.

Anthropic API 가격 정책 (USD per 1M tokens, **2026-09 기준**):
  - Fable : $10 input / $50 output (Fable 5.1 — 최고 난도 추론)
  - Opus  : $5 input / $25 output  (Opus 5/4.8/4.7 — 2026-07 에 $15/$75 대비 3× 인하)
  - Sonnet: $2 input / $10 output  ← 기본값 (claude-sonnet-5). 🔴 4.6 세대는 $3/$15 였다 — 세대가
            오르며 «내렸다». ID 만 올리고 요율을 두면 추정이 50% 과대가 된다.
  - Haiku : $1 input / $5 output   (Haiku 4.5 — 현행 최신)

⚠️ **정확도 경고**:
  - 가격은 Anthropic 측 변경 가능 — **분기별 (3개월) 재확인 필수**.
  - 추세 추적용 추정이므로 실제 청구 대비 ±10% 오차 허용.
  - 월별 실제 청구액 vs 본 모듈 합계 차이 10% 초과 시 즉시 가격표 갱신.
  - 미지의 모델 이름은 sonnet 요율로 fallback — typo 시 과소/과대 추정 가능.
"""
import inspect
import logging
import re
import threading
from dataclasses import dataclass
from datetime import datetime

import anthropic

from src.constants import CLAUDE_RETIRED_MODEL_PRICING
from src.shared import model_catalog as mc
from src.shared.log_safety import sanitize_for_log

logger = logging.getLogger(__name__)

# anthropic SDK 가 따를 Retry-After 상한(초) — SDK ≥1.6 은 상한 없이 기다린다 (#1690).
#   파이프라인 60s = 1.5.0 의 판정값(`0 < retry_after <= 60`). 슬롯 최악 90×2 + 60 = 240s.
#   페이지 15s = 사용자 요청 안의 대기라 더 짧다. 페이지 호출 전체는 아래 기한이 끊는다(#1697).
# Retry-After cap the SDK may honour (SDK >= 1.6 waits unbounded). Pipeline keeps 1.5.0's 60s;
# the page routes wait inside a user request, so they get 15s.
ANTHROPIC_RETRY_AFTER_CAP_PIPELINE_SECONDS = 60.0
ANTHROPIC_RETRY_AFTER_CAP_PAGE_SECONDS = 15.0
# 페이지 Claude 호출 전체 기한(초) — 시도·backoff·Retry-After 대기를 모두 묶는다 (#1697).
#   실측(Haiku 4.5 · 출력 1201~1800 토큰 · n=141): p50 16.2s · p90 31.6s · p99 39.0s.
#   단일 시도는 ~p99 까지 통과, 15s Retry-After 를 따른 뒤의 재시도는 ~p90 부터 끊긴다.
#   시도당 읽기 타임아웃(60s)보다 짧아야 멈춘 첫 시도를 끊는다.
# Total page-call deadline. Measured (Haiku 4.5, 1201-1800 output tokens, n=141): p50 16.2s,
# p90 31.6s, p99 39.0s. A single attempt passes to ~p99; a retry after an honoured 15s
# Retry-After is cut from ~p90. It must stay below the 60s per-attempt timeout.
ANTHROPIC_PAGE_DEADLINE_SECONDS = 45.0


def _sdk_will_retry(response) -> bool:
    """SDK `_should_retry` 와 같은 **응답** 판정 — 이 판정이 거짓인 응답은 건드리지 않는다.
    남은 재시도 수는 보지 않는다 — 마지막 시도도 참이면 재작성·기록되고, 그때는 대기가 없다.
    Response-level mirror of the SDK's `_should_retry`; it ignores the remaining retry count,
    so the final attempt is rewritten and logged too (no backoff follows it).
    """
    flag = response.headers.get("x-should-retry")
    if flag in ("true", "false"):
        return flag == "true"
    return response.status_code in (408, 409, 429) or response.status_code >= 500


def _retry_after_within_cap(headers, cap: float) -> bool:
    """SDK 와 같은 순서(`retry-after-ms` → `retry-after`)·같은 `float()` 로 읽어 상한 이하가
    **증명될 때만** True. 날짜·쓰레기·inf·nan 은 상한 초과로 본다 — 틀려도 대기가 짧아진다.
    True only when provably <= cap, parsed like the SDK; anything else counts as over the cap.
    """
    ms = headers.get("retry-after-ms")
    if ms is not None:
        try:
            return float(ms) / 1000 <= cap
        except ValueError:
            pass
    raw = headers.get("retry-after")
    if raw is None:
        return True
    try:
        return float(raw) <= cap
    except ValueError:
        return False


class _RetryAfterCap(anthropic.Middleware):  # pylint: disable=too-few-public-methods
    """상한을 넘는 Retry-After 를 무효화한다 — SDK 가 재시도하면 자체 backoff(0.375~8s)를 쓴다 (#1690).

    `_sdk_will_retry` 가 참인 응답에 `retry-after-ms: 0` 을 쓴다 — SDK 가 먼저 읽고 0 은 `> 0` 을
    못 넘는다. 남은 재시도 수는 보지 않으므로 **마지막 시도**도 재작성·기록되고, 그 응답은 대기
    없이 예외가 된다(예외 헤더에 `retry-after-ms: 0` 이 남는다). `retry-after` 는 절대 바꾸지
    않아 `error_retry_after` 는 벤더 원문 그대로다.
    🔴 이 미들웨어(와 안쪽 미들웨어)는 APIStatusError 를 raise 하지 않는다 — 그 경로는 재작성을 우회한다.
    Neutralises an over-cap Retry-After; if the SDK retries, it uses its own backoff. The final
    attempt is rewritten and logged too and becomes the exception with no wait; `retry-after`
    itself is never modified.
    Never raise APIStatusError from this or an inner middleware: that path bypasses the rewrite.
    """

    def __init__(self, *, caller: str, retry_after_cap: float) -> None:
        self._caller = caller
        self.retry_after_cap = retry_after_cap

    async def handle_async(self, request, call_next):
        response = await call_next(request)
        http = response.http_response
        if (not http.is_success and _sdk_will_retry(http)
                and not _retry_after_within_cap(http.headers, self.retry_after_cap)):
            logger.warning(
                "anthropic Retry-After 상한 초과 → retry-after-ms 0 (재시도하면 SDK backoff) / "
                "Retry-After over cap, retry-after-ms set to 0 (SDK backoff if it retries): "
                "caller=%s status=%d attempt=%d cap=%g retry_after=%s retry_after_ms=%s request_id=%s",
                self._caller, http.status_code, request.retries_taken + 1, self.retry_after_cap,
                sanitize_for_log(http.headers.get("retry-after"), max_len=64),
                sanitize_for_log(http.headers.get("retry-after-ms"), max_len=64),
                sanitize_for_log(http.headers.get("request-id"), max_len=64),
            )
            http.headers["retry-after-ms"] = "0"
        return response


def new_async_anthropic(
    *, api_key: str, timeout: float, max_retries: int, caller: str, retry_after_cap: float,
) -> anthropic.AsyncAnthropic:
    """AsyncAnthropic 생성 단일 지점 — Retry-After 상한 미들웨어를 붙인다 (#1690).
    클래스를 호출 시점에 조회한다 — 기존 `patch(...anthropic.AsyncAnthropic)` 더블이 그대로 가로챈다.
    Single construction point; the class is looked up at call time so patch doubles still intercept.
    """
    return anthropic.AsyncAnthropic(
        api_key=api_key, timeout=timeout, max_retries=max_retries,
        middleware=[_RetryAfterCap(caller=caller, retry_after_cap=retry_after_cap)],
    )


def release_session_before_claude(db) -> None:
    """Claude 를 기다리기 전에 요청 세션의 트랜잭션을 끝내 풀 연결을 돌려준다 (#1697).

    await 동안 연결을 쥐면 풀이 차고, 다음 요청의 동기 체크아웃이 이벤트 루프 자체를
    `pool_timeout` 만큼 멈춘다(쥔 쪽도 재개하지 못해 풀어 주지 못한다).
    🔴 호출부의 미완료 쓰기는 커밋하지 않고 **거부**한다 — 건너뛰어도 뒤따르는 캐시 쓰기가
    스스로 커밋하므로 멈추는 것만이 막는다. 이미 flush 된 쓰기는 이 검사가 못 본다.
    Ends the request session's transaction so no pooled connection is held across the Claude
    await. Raises instead of committing a caller's pending writes (skipping would not help: the
    later cache writes commit themselves). Already-flushed writes are invisible to this check.
    """
    pending = len(db.new) + len(db.dirty) + len(db.deleted)
    if pending:
        raise RuntimeError(
            f"{pending} pending ORM change(s) in the request session — commit or roll back "
            "before the Claude call; the insight service will not commit them for you"
        )
    db.commit()


async def aclose_anthropic_client(client) -> None:
    """호출당 생성한 AsyncAnthropic(httpx 풀)를 안전 종료 — awaitable 일 때만 await (WBS P1 누수 차단).

    🔴 종료 메서드 이름은 `close()` 다. `aclose` 는 anthropic 0.60.0~1.0.0 **어느 판에도 없다**
    (실측). `aclose` 만 찾던 이전 구현은 실 SDK 앞에서 늘 no-op 였고, 더블이 없는 속성도
    자동 생성하는 MagicMock 이라 테스트는 6월부터 계속 초록이었다. 그러니 `close` 를 먼저 본다.
    `aclose` 폴백은 그 이름을 쓰는 httpx 계열 객체를 위해 남긴다. 둘 다 없으면 **조용히
    넘어가지 않는다** — 못 닫았다는 사실이 로그에 남아야 다음 사람이 안다.

    The real close method is `close()`; `aclose` exists on no anthropic 0.60.0-1.0.0 client, so
    the previous aclose-only lookup was always a no-op that MagicMock doubles could not detect.
    Look up `close` first, keep `aclose` as an httpx-style fallback, and warn when neither exists.
    """
    closer = getattr(client, "close", None)
    if closer is None:
        closer = getattr(client, "aclose", None)
    if closer is None:
        logger.warning(
            "커넥션 풀을 닫지 못했다 — close/aclose 둘 다 없음 (type=%s). "
            "Could not close the connection pool: neither close nor aclose exists.",
            type(client).__name__,
        )
        return
    result = closer()
    if inspect.isawaitable(result):
        # 맨 `await result` 는 CodeQL 이 효과 없는 문장(py/ineffectual-statement)으로 본다 — 기각(#567)은
        # 줄이 옮겨지면 새 알림(#614)으로 되살아나 코드로 끝낸다.
        # A bare `await result` trips CodeQL py/ineffectual-statement; a dismissal reappears when the
        # line moves (#567 -> #614), so bind the result instead.
        _ = await result

# 판마다 요율 (USD per 1M tokens) — Anthropic 요율(claude-api 참조 2026-11) · 키는 별칭(날짜 접미사 없는 id) (#1905 ②).
# Per-model rates (USD per 1M tokens), Anthropic pricing as of 2026-11; keys are aliases without a date suffix.
# 🔴 PARITY GUARD: 이 표가 가격 SSOT 다. 선택지 판(constants.CLAUDE_MODELS)의 가격 · i18n model_hint(en/ko/ja)를
#   tests/unit/shared/test_pricing_parity.py 가 이 표와 대조한다 — 하나만 고치면 CI 에서 red(정책 4).
# 🔴 PARITY GUARD: this table is the pricing SSOT; the selector prices and the i18n hint are checked against it.


@dataclass(frozen=True)
class ModelRate:
    """판 하나의 요율 — 구간 요율은 프롬프트(입력 + 캐시 읽기 + 캐시 쓰기) 길이로 요청 전체에 건다.

    One model's rate; a tier applies to the whole request by prompt size (input + cache reads + cache writes).
    `cache_read` 가 없으면 입력 요율 × 0.1 / without `cache_read` a cache read costs input × 0.1.
    """

    input: float
    output: float
    cache_read: float | None = None
    tier_threshold_tokens: int | None = None
    tier_input: float | None = None
    tier_output: float | None = None


_MODEL_RATES: dict[str, ModelRate] = {
    "claude-haiku-4-5": ModelRate(1.0, 5.0),
    # Haiku 5.5 — 프롬프트 100K 토큰 이하 $0.10/$0.50, 넘으면 요청 전체 $0.50/$2.50
    # Haiku 5.5: $0.10/$0.50 up to a 100K-token prompt, $0.50/$2.50 for the whole request above it.
    "claude-haiku-5-5": ModelRate(0.10, 0.50, tier_threshold_tokens=100_000, tier_input=0.50, tier_output=2.50),
    # 🔴 Sonnet 5 는 (2.0, 10.0) 이다 — 4.6 세대의 (3.0, 15.0) 이 아니다(2026-09 공식 문서 실측).
    # Sonnet 5 is $2/$10, not the 4.6-generation $3/$15.
    "claude-sonnet-5": ModelRate(2.0, 10.0),
    "claude-sonnet-5-5": ModelRate(2.0, 10.0, cache_read=0.10),
    # Opus 4.8 — 서버 대체가 답할 수 있는 판이라 hop 비용 행이 이 이름으로 온다
    # Opus 4.8: a server fallback may answer with it, so hop cost rows can carry this id.
    "claude-opus-4-8": ModelRate(5.0, 25.0),
    # Opus 4.7 — 운영 리포가 고정했던 적이 있다(회고 2026-09-16 K09) · 요율은 Opus 5 와 같다(2026-07 확인)
    # Opus 4.7: once pinned by a production repo (K09); same rate as Opus 5 (confirmed 2026-07).
    "claude-opus-4-7": ModelRate(5.0, 25.0),
    "claude-opus-5": ModelRate(5.0, 25.0),
    "claude-opus-5-5": ModelRate(4.0, 20.0, cache_read=0.20),
    "claude-fable-5-1": ModelRate(10.0, 50.0, cache_read=0.25),
    "claude-fable-5-2": ModelRate(8.0, 40.0, cache_read=0.20),
    # 내린 판 — 선택지에는 없지만 저장된 값이 계속 흐른다(`constants.CLAUDE_RETIRED_MODEL_PRICING`)
    # Retired models: not offered, but stored values still flow.
    **{model_id: ModelRate(rates["input"], rates["output"])
       for model_id, rates in CLAUDE_RETIRED_MODEL_PRICING.items()},
}
_DATED_SUFFIX = re.compile(r"-\d{8}$")
# 계열을 모르는 판은 sonnet 계열로 보수적으로 추정 / a model of no known line is estimated as sonnet
_DEFAULT_LINE = "sonnet"


def _newest_rate_by_line() -> dict[str, ModelRate]:
    """계열마다 기본 카탈로그에서 가장 새 판의 요율 — 표에 없는 판을 «추정» 할 때 쓴다.

    Per line, the rate of the newest fallback-catalog model; used to estimate models missing from the table.
    """
    newest: dict[str, tuple[datetime, ModelRate]] = {}
    for entry in mc.FALLBACK_CATALOG:
        rate = _MODEL_RATES.get(entry.id)
        held = newest.get(entry.line or "")
        if rate is not None and entry.line and (held is None or entry.created_at > held[0]):
            newest[entry.line] = (entry.created_at, rate)
    return {line: rate for line, (_, rate) in newest.items()}


_NEWEST_RATE_BY_LINE = _newest_rate_by_line()


def _rate_for(model: str) -> tuple[ModelRate, bool]:
    """판 id → (요율, 추정인가) — 별칭(날짜 접미사를 뗀 id)으로 찾고, 없으면 같은 계열의 가장 새 판 요율.

    Model id -> (rate, estimated?): looked up by alias; otherwise the newest rate of the same line.
    """
    key = _DATED_SUFFIX.sub("", (model or "").strip().lower())
    rate = _MODEL_RATES.get(key)
    if rate is not None:
        return rate, False
    line = mc.line_of(key) if key else None
    return _NEWEST_RATE_BY_LINE.get(line or "", _NEWEST_RATE_BY_LINE[_DEFAULT_LINE]), True


def is_estimated_rate(model: str) -> bool:
    """요율표에 없는 판인가 — 같은 계열의 가장 새 판 요율로 «추정» 한 비용이다.

    Whether the model is missing from the rate table, i.e. its cost is estimated from the line's newest rate.
    """
    return _rate_for(model)[1]


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
    """판 + 토큰 수로 USD 비용 — 판 단위 요율(구간 · 판별 캐시 읽기) · 표에 없는 판은 같은 계열의 가장 새 판 요율로 추정.

    Estimate USD cost from model + tokens: per-model rates (tiers, per-model cache reads); a model missing from the
    table is estimated with its line's newest rate (`is_estimated_rate`).
    캐시 읽기 = 표의 값 또는 입력 × 0.1 · 캐시 쓰기 = 입력 × 1.25(5분) / cache read = table or input × 0.1.
    🔴 계열(부분문자열)이 아니라 판 id 가 먼저다 — 계열은 세대를 구분하지 못해 내린 Sonnet 4.6($3/$15)을
    Sonnet 5($2/$10)로 매겼다. 저장된 `RepoConfig.review_model` 은 검증 없이 흐르므로 이 경로가 실제로 열려 있다.
    The model id wins over the line: a line cannot tell generations apart.
    """
    rate, _ = _rate_for(model)
    prompt_tokens = input_tokens + cache_read_tokens + cache_creation_tokens
    if rate.tier_threshold_tokens is not None and prompt_tokens > rate.tier_threshold_tokens:
        in_rate = rate.tier_input if rate.tier_input is not None else rate.input
        out_rate = rate.tier_output if rate.tier_output is not None else rate.output
        cache_read_rate = in_rate * _CACHE_READ_MULTIPLIER
    else:
        in_rate, out_rate = rate.input, rate.output
        cache_read_rate = rate.cache_read if rate.cache_read is not None else in_rate * _CACHE_READ_MULTIPLIER
    return (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * cache_read_rate
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
_silent_fallback_streak: int = 0  # 연속 creation>0 + read==0 카운터  # pylint: disable=invalid-name
_stats_lock = threading.Lock()


def reset_cache_stats() -> None:
    """카운터 초기화 — 테스트 격리 + 운영 수동 리셋용.

    Reset counters — for test isolation and operational manual reset.
    """
    global _silent_fallback_streak  # pylint: disable=global-statement
    with _stats_lock:
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


def log_claude_api_call(  # pylint: disable=too-many-arguments
    *,
    model: str,
    duration_ms: float,
    input_tokens: int,
    output_tokens: int,
    status: str,
    error_type: str = "",
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    repo_id: int | None = None,
    user_id: int | None = None,
) -> None:
    """Claude API 호출 1건의 구조화된 메트릭 로그.

    LogRecord extra 로 필드를 첨부해 structured log shipper (CloudWatch / Railway 등)
    가 파싱할 수 있도록 한다.

    Args:
        model: 호출된 모델 ID (예: "claude-sonnet-5")
        duration_ms: API 호출 전체 소요 시간 (ms)
        input_tokens / output_tokens: 입력/출력 토큰 수.
            🔴 **에러라고 0 을 넘기지 말 것** (backlog R65). API 가 응답을 돌려준 뒤
            추출·파싱이 실패한 경우 토큰은 **이미 과금**됐다 — 0 으로 적으면
            `monthly_cost` 가 과소 계상된다. 호출 자체가 실패해 토큰을 모르는
            경우에만 0 이다.
            Do not zero these on failure: tokens are billed once the API responded.
            0 is correct only when the call itself failed.
        status: "success" | "error". 페이지 기한 초과도 "error" + error_type "TimeoutError" 다.
            A page-deadline miss is also "error" with error_type "TimeoutError".
        error_type: 에러 타입 이름 (status=="error" 일 때)
        cache_read_tokens: prompt cache 에서 읽은 토큰 수 (기본 0).
            Anthropic 정가 대비 1/10 비용으로 청구됨.
            Cached tokens read from prompt cache (10× cheaper than fresh input).
        cache_creation_tokens: prompt cache 생성 토큰 수 (기본 0).
            정가 대비 1.25× 비용 (캐시 등록 비용 — 5분 TTL 내 재사용 시 절감 회수).
            Tokens written to prompt cache (1.25× normal cost; recouped on hits).
        repo_id: 비용 귀속 대상 리포 id (기본 None — 시스템/미귀속 호출).
            Repo id to attribute cost to (default None — system/unattributed call).
        user_id: 비용 귀속 대상 사용자 id (기본 None).
            User id to attribute cost to (default None).
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
    # 누적 카운터 갱신 — silent fallback 차단 streak 추적 페어. 인사이트 페이지는 이 함수를
    #   워커 스레드에서 부르므로(#1701) 읽고-더하고-쓰기를 잠금 안에서 한다.
    # Update cumulative counters (silent-fallback streak pair) under a lock: the insight pages
    #   call this from worker threads.
    global _silent_fallback_streak  # pylint: disable=global-statement
    with _stats_lock:
        _cache_stats["total_calls"] += 1
        _cache_stats["cache_read_tokens"] += cache_read_tokens
        _cache_stats["cache_creation_tokens"] += cache_creation_tokens
        _cache_stats["input_tokens"] += input_tokens
        if status == "success":
            if cache_creation_tokens > 0 and cache_read_tokens == 0:
                _silent_fallback_streak += 1
            else:
                _silent_fallback_streak = 0
        streak = _silent_fallback_streak
        if status == "success" and streak >= _SILENT_FALLBACK_THRESHOLD:
            _silent_fallback_streak = 0  # 재 alert 방지
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
        if streak >= _SILENT_FALLBACK_THRESHOLD:
            logger.warning(
                "claude_api_call silent_cache_fallback streak=%d "
                "(cache_creation>0 + cache_read=0 N회 연속 — system_text 1024 토큰 미달 가능)",
                streak,
            )
    else:
        # 🔴 실패 행도 토큰·비용을 **사람이 읽는 줄에** 싣는다 (backlog R65). `extra` 에만
        # 있으면 로그 shipper 를 안 거치는 운영자에게는 실패의 비용이 보이지 않는다.
        # Surface tokens/cost on the human-readable line too — `extra` alone is invisible
        # to an operator reading raw logs.
        logger.warning(
            "claude_api_call model=%s duration_ms=%.0f input_tokens=%d output_tokens=%d "
            "cost_usd=%.4f status=%s error_type=%s",
            model, duration_ms, input_tokens, output_tokens, cost_usd, status, error_type,
            extra=extra,
        )

    # 비용 영속화 — fail-safe(DB 에러가 API 흐름을 절대 차단하지 않음).
    # Cost persistence — fail-safe (a DB error must never break the API flow).
    try:
        _persist_cost(
            model=model, status=status, input_tokens=input_tokens, output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens, cache_creation_tokens=cache_creation_tokens,
            cost_usd=cost_usd, duration_ms=duration_ms,
            repo_id=repo_id, user_id=user_id, error_type=error_type,
        )
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        logger.warning("claude_api_call cost persistence skipped (fail-safe): %s", exc)


def _persist_cost(*, model, status, input_tokens, output_tokens,  # pylint: disable=too-many-arguments
                  cache_read_tokens, cache_creation_tokens, cost_usd, duration_ms,
                  repo_id, user_id, error_type):
    """단발 WorkerSessionLocal 세션으로 비용 1행 INSERT (호출자가 fail-safe 로 감쌈).
    RLS 우회 필요 — claude_api_calls 정책은 repo_id/user_id 미설정(system 호출) 행만
    app.user_id 무관 허용하고, 설정된 행은 세션 컨텍스트 일치를 요구한다(0043). 호출 시점이
    웹 요청/백그라운드 어느 쪽이든 이 메트릭 write 는 세션 컨텍스트와 무관하게 성공해야 하므로
    BYPASSRLS worker 세션을 일관 사용한다 — alias(`as SessionLocal`) 는 background 모듈
    컨벤션(db.md) 과 동일한 patch 대상 심볼명 유지 목적.
    Insert one cost row via a short-lived WorkerSessionLocal (caller wraps fail-safe).
    RLS bypass is required — the claude_api_calls policy (0043) only allows session-context-
    independent rows when repo_id/user_id are unset (system calls); rows with either set require
    a matching session context. Since this metric write must succeed regardless of whether the
    caller runs in a web request or background context, it consistently uses the BYPASSRLS worker
    session — aliased (`as SessionLocal`) to keep the same patch-target symbol name as other
    background modules (db.md convention)."""
    # noqa: PLC0415  # pylint: disable=import-outside-toplevel
    from src.database import WorkerSessionLocal as SessionLocal
    from src.repositories import claude_api_cost_repo
    with SessionLocal() as db:
        claude_api_cost_repo.record(
            db, model=model, status=status, input_tokens=input_tokens, output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens, cache_creation_tokens=cache_creation_tokens,
            cost_usd=cost_usd, duration_ms=duration_ms, repo_id=repo_id, user_id=user_id,
            error_type=error_type,
        )
