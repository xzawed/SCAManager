"""AI code review using the Anthropic Claude API.

Tier 3 PR-A 후속 (Phase 1 PR #3) — Anthropic prompt caching 도입:
시스템 프롬프트(채점 가이드 + JSON 형식 명세, ~600-800 tokens) 를
`cache_control={"type": "ephemeral"}` 로 마크해 5분 캐시. 동일 시스템
프롬프트가 5분 내 재사용되면 input 토큰 비용이 1/10 (cache read).

Anthropic prompt caching adopted: the system prompt (~600-800 tokens)
is marked `cache_control={"type": "ephemeral"}` so input cost drops 10× on
cache hit (5-minute TTL).
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field

import anthropic

from src.analyzer.pure.review_prompt import build_review_prompt, get_system_prompt
from src.config import settings
from src.constants import (
    AI_DEFAULT_COMMIT_RAW, AI_DEFAULT_DIRECTION_RAW, AI_DEFAULT_TEST_RAW,
    AI_RAW_COMMIT_MAX, AI_RAW_DIRECTION_MAX, AI_RAW_TEST_MAX,
)
from src.shared.anthropic_caching import build_cached_system_param
from src.shared.claude_metrics import aclose_anthropic_client, extract_anthropic_usage, log_claude_api_call

logger = logging.getLogger(__name__)


@dataclass
class AiReviewResult:  # pylint: disable=too-many-instance-attributes
    """Structured result from the Claude AI code review, including scores and per-category feedback."""
    commit_score: int        # 0-20: 커밋 메시지 품질
    ai_score: int            # 0-20: 구현 방향성
    test_score: int          # 0-10: 테스트 커버리지 점수
    summary: str
    suggestions: list[str] = field(default_factory=list)
    commit_message_feedback: str = ""    # 커밋 메시지 평가 상세
    code_quality_feedback: str = ""      # 코드 품질 평가 상세
    security_feedback: str = ""          # 보안 평가 상세
    direction_feedback: str = ""         # 구현 방향성 평가 상세
    test_feedback: str = ""              # 테스트 평가 상세
    file_feedbacks: list[dict] = field(default_factory=list)  # 파일별 피드백
    status: str = "success"  # "success" | "no_api_key" | "empty_diff" | "api_error" | "parse_error"
    detected_languages: list[str] = field(default_factory=list)  # 감지된 언어 목록
    # Anthropic API 실제 토큰 사용량 — 비용 추적용 (0 = API 미호출 또는 오류)
    # Actual Anthropic API token usage — for cost tracking (0 = not called or error)
    input_tokens: int = 0
    output_tokens: int = 0
    # 실제 사용된 모델명 — None = 전역 기본값 사용
    # Actual model used — None means global default was used
    used_model: str | None = None


async def review_code(  # pylint: disable=too-many-locals  # 다국어 + caching + 예외 분기로 인한 누적 (사이클 84 i18n)
    api_key: str,
    commit_message: str,
    patches: list[tuple[str, str]],
    language: str = "en",
    model: str | None = None,
) -> AiReviewResult:
    """Claude API로 코드를 리뷰하고 점수를 반환한다. API key가 없으면 기본값 반환.

    Phase 4 PR-12 (사이클 84) — language 인자 추가. system prompt 가 출력 언어를 결정 (en/ko/ja).
    Anthropic prompt cache key = system text hash → language 별 system text 다름 → 자동 cache 분기.

    Phase 4 PR-12 (Cycle 84) — language arg added. System prompt determines output language.
    Cache key (system text hash) auto-diverges per language → independent cache per language.
    """
    if not api_key:
        return _default_result("no_api_key")

    prompt, languages = build_review_prompt(commit_message, patches, language=language)

    if not prompt.strip():
        return _default_result("empty_diff")

    # diff 유무 확인 — build_review_prompt가 diff_text를 포함하므로 "(없음)" 체크
    diff_text = "\n".join(
        f"--- {fname}\n{patch}" for fname, patch in patches
    )
    if not diff_text.strip():
        return _default_result("empty_diff")

    # Anthropic SDK 기본 timeout=600s 는 BackgroundTask 슬롯을 10분 점유 위험.
    # HTTP_CLIENT_TIMEOUT 보다 여유 두고 60s 로 설정 — 평균 응답 5-15s 대비 충분.
    # max_retries=2 — SDK 기본값 명시화. 5xx / connection error / timeout 시 SDK 가
    # exponential backoff 으로 자동 재시도. SDK 업그레이드로 기본값 변경되면
    # 운영 영향 — 명시적 인자로 면역. tests/unit/analyzer/io/test_ai_review_errors.py
    # ::test_review_code_passes_explicit_max_retries_to_anthropic_client 회귀 가드.
    # Default SDK timeout (600s) can occupy a BackgroundTask slot for 10 min.
    # Set 60s — well above typical 5-15s response, far below SDK default.
    # max_retries=2 — explicit so SDK upgrades cannot silently change retry behavior.
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=60.0, max_retries=2)
    model = model or settings.claude_review_model
    # Phase 4 PR-12 — language 별 system prompt (출력 언어 지시 포함).
    # Phase 4 PR-12 — per-language system prompt (with output language directive).
    system_text = get_system_prompt(language)
    start = time.perf_counter()
    try:
        # 시스템 프롬프트에 cache_control 적용 — 5분 ephemeral 캐시 (공용 헬퍼 경유).
        # `settings.disable_prompt_cache=True` 시 운영 opt-out (cache_control 미적용).
        # System prompt with cache_control (ephemeral 5-min) via shared helper.
        # `settings.disable_prompt_cache=True` opts out (cache_control omitted).
        response = await client.messages.create(
            model=model,
            max_tokens=1500,
            system=build_cached_system_param(system_text),
            messages=[{"role": "user", "content": prompt}],
        )
        duration_ms = (time.perf_counter() - start) * 1000
        input_tokens, output_tokens = extract_anthropic_usage(response)
        # 캐시 토큰 추출 — 관측성용 (Anthropic 응답에 cache_*_input_tokens 필드 존재 시)
        # Extract cache token counts when present in the response (observability)
        usage = getattr(response, "usage", None)
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_creation = getattr(usage, "cache_creation_input_tokens", 0) or 0
        log_claude_api_call(
            model=model,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="success",
            cache_read_tokens=cache_read,
            cache_creation_tokens=cache_creation,
        )
        result = _parse_response(response.content[0].text)
        result.detected_languages = languages
        result.input_tokens = input_tokens
        result.output_tokens = output_tokens
        result.used_model = model
        return result
    except Exception as exc:  # pylint: disable=broad-exception-caught  # noqa: BLE001
        # anthropic/httpx 는 다양한 예외를 발생시킬 수 있음 — 모두 graceful fallback
        duration_ms = (time.perf_counter() - start) * 1000
        log_claude_api_call(
            model=model,
            duration_ms=duration_ms,
            input_tokens=0,
            output_tokens=0,
            status="error",
            error_type=type(exc).__name__,
        )
        logger.exception("AI review failed, using default scores")
        return _default_result("api_error")
    finally:
        # 호출당 생성한 AsyncAnthropic httpx 커넥션 풀 해제 — 미종료 시 FD 누수 (WBS P1).
        # Close the per-call AsyncAnthropic httpx pool — leaks FDs/connections if left open.
        await aclose_anthropic_client(client)


def _coerce_score(raw: object, max_val: int, default: int) -> "tuple[int, bool]":
    """raw 점수를 [0, max_val] 정수로 안전 클램프 — 비숫자/Infinity 시 default 폴백 + ok=False.
    Safely clamp a raw score to [0, max_val]; fall back to default on non-numeric/Infinity (ok=False).

    🔴 PARITY GUARD: src/api/hook.py::_coerce_raw_score 와 행동 동등(반환 (int, ok)). 둘 중 하나
    변경 시 양쪽 동시 수정 + parity 회귀 가드(test_ai_review_errors.py) 갱신 의무 (testing.md
    의도적 중복 패턴 — 사용처 2곳이라 공유 추출 대신 인라인+가드, 정책16 최소 추상화).
    int(raw) 가 TypeError/ValueError(float-string)/OverflowError(Infinity)를 던지면 default·ok=False.
    유효한 float(예: 8.9)은 int() 가 0 방향 절삭(양수=floor, 반올림 X) → 8 — 점수 보수적 하향(인플레 방지), ok=True.
    A valid float (e.g. 8.9) is truncated toward zero by int() (floor for positives, no rounding) → 8 (ok=True).
    🔴 PARITY GUARD with src/api/hook.py::_coerce_raw_score — keep behaviour identical; update both
    plus the parity regression test together when changing either.
    """
    try:
        value = int(raw)
    except (TypeError, ValueError, OverflowError):
        return max(0, min(max_val, default)), False
    return max(0, min(max_val, value)), True


def _coerce_test_score(data: dict) -> "tuple[int, bool]":
    """test_score 안전 추출 (int, ok). 구 포맷(has_tests boolean) 하위 호환 — 키 부재는 ok=True."""
    if "test_score" in data:
        return _coerce_score(data["test_score"], AI_RAW_TEST_MAX, AI_DEFAULT_TEST_RAW)
    return (AI_RAW_TEST_MAX if data.get("has_tests", False) else 0), True


def _extract_test_score(data: dict) -> int:
    """test_score 추출(int) — 하위 호환 wrapper. 안전 변환·ok 플래그는 _coerce_test_score 사용."""
    return _coerce_test_score(data)[0]


def _extract_json_payload(text: str) -> str:
    """Claude 응답에서 JSON 페이로드만 추출.

    우선순위: (1) ```json/```JSON 코드 블록 → (2) 첫 `{` ~ 마지막 `}` 구간.
    Claude 가 종종 preamble 또는 trailing text 를 붙이거나 언어 태그 대소문자를
    섞어 응답 — 프로덕션 분석 #543 "parse_error" 원인.
    """
    cleaned = text.strip()
    block_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        cleaned,
        re.DOTALL | re.IGNORECASE,
    )
    if block_match:
        return block_match.group(1)
    first = cleaned.find("{")
    last = cleaned.rfind("}")
    if first != -1 and last > first:
        return cleaned[first:last + 1]
    return cleaned


def _parse_response(text: str) -> AiReviewResult:
    try:
        data = json.loads(_extract_json_payload(text))
    except json.JSONDecodeError:
        # 진짜 구조 붕괴(JSON 파싱 실패)만 전량 parse_error — 점수 필드 문제는 아래서 per-field 흡수.
        # Only genuine structural failure (JSON decode) collapses to parse_error; score-field issues
        # are absorbed per-field below.
        logger.warning("Failed to parse AI review response: %s", text[:200])
        return _default_result("parse_error")
    if not isinstance(data, dict):
        # JSON array/scalar 등 비-dict 페이로드 — data.get 불가 → parse_error
        # Non-dict payload (array/scalar) — data.get unavailable → parse_error
        logger.warning("AI review response is not a JSON object: %s", text[:200])
        return _default_result("parse_error")
    # 🔴 #24: 점수 필드 per-field 안전 변환 — 단일 필드 float-string("88.0")/Infinity 가 리뷰 전체
    # (복구 가능한 점수 + 모든 feedback 텍스트)를 붕괴시키지 않도록 한다. hook.py _coerce_raw_score
    # 하드닝(#784)과 대칭(PARITY GUARD).
    # #24: per-field score coercion so one bad numeric field (float-string/Infinity) doesn't collapse
    # the whole review (recoverable scores + all feedback text); mirrors hook.py _coerce_raw_score.
    commit, commit_ok = _coerce_score(
        data.get("commit_message_score", AI_DEFAULT_COMMIT_RAW), AI_RAW_COMMIT_MAX, AI_DEFAULT_COMMIT_RAW)
    direction, direction_ok = _coerce_score(
        data.get("direction_score", AI_DEFAULT_DIRECTION_RAW), AI_RAW_DIRECTION_MAX, AI_DEFAULT_DIRECTION_RAW)
    test, test_ok = _coerce_test_score(data)
    result = AiReviewResult(
        commit_score=commit,
        ai_score=direction,
        test_score=test,
        summary=str(data.get("summary", "")),
        suggestions=[str(s) for s in data.get("suggestions", [])],
        commit_message_feedback=str(data.get("commit_message_feedback", "")),
        code_quality_feedback=str(data.get("code_quality_feedback", "")),
        security_feedback=str(data.get("security_feedback", "")),
        direction_feedback=str(data.get("direction_feedback", "")),
        test_feedback=str(data.get("test_feedback", "")),
        file_feedbacks=list(data.get("file_feedbacks", [])),
    )
    if not (commit_ok and direction_ok and test_ok):
        # 점수 필드 비숫자/Infinity — feedback·복구가능 점수는 보존하되 parse_error 로 표시해
        # #804(#8) ai_review_failed 게이트의 fail-closed(auto-merge/approve 차단)를 유지한다.
        # (이전: 전량 _default_result 로 feedback 까지 폐기. 게이트 동작은 동일, 데이터만 보존.)
        # Non-numeric/Infinity score field: keep feedback/recoverable scores but mark parse_error so
        # the #804 gate stays fail-closed (was: total discard via _default_result; gate behaviour
        # unchanged, only the data is preserved).
        result.status = "parse_error"
    return result


def _default_result(reason: str = "no_api_key") -> AiReviewResult:
    """API key 없음, 빈 diff, 또는 오류 시 반환하는 중립적 기본값."""
    # summary 는 빈 문자열 — 발신 시 status 기반으로 notifier 가 현지화 메시지 대체
    # (notifier._common.resolve_ai_summary). 대시보드는 ai_review_status 로 별도 i18n 배너 렌더.
    # summary stays empty — notifiers localize via status (resolve_ai_summary);
    # the dashboard renders its own i18n banner from ai_review_status (사이클 155 P1).
    return AiReviewResult(
        commit_score=17,
        ai_score=17,
        test_score=7,
        summary="",
        suggestions=[],
        status=reason,
    )
