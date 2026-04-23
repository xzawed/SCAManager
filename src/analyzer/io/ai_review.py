"""AI code review using the Anthropic Claude API."""
import json
import logging
import re
import time
from dataclasses import dataclass, field

import anthropic

from src.analyzer.pure.review_prompt import build_review_prompt
from src.config import settings
from src.constants import AI_DEFAULT_COMMIT_RAW, AI_DEFAULT_DIRECTION_RAW, AI_RAW_COMMIT_MAX, AI_RAW_DIRECTION_MAX
from src.shared.claude_metrics import extract_anthropic_usage, log_claude_api_call

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


async def review_code(
    api_key: str,
    commit_message: str,
    patches: list[tuple[str, str]],
) -> AiReviewResult:
    """Claude API로 코드를 리뷰하고 점수를 반환한다. API key가 없으면 기본값 반환."""
    if not api_key:
        return _default_result("no_api_key")

    prompt, languages = build_review_prompt(commit_message, patches)

    if not prompt.strip():
        return _default_result("empty_diff")

    # diff 유무 확인 — build_review_prompt가 diff_text를 포함하므로 "(없음)" 체크
    diff_text = "\n".join(
        f"--- {fname}\n{patch}" for fname, patch in patches
    )
    if not diff_text.strip():
        return _default_result("empty_diff")

    client = anthropic.AsyncAnthropic(api_key=api_key)
    model = settings.claude_review_model
    start = time.perf_counter()
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        duration_ms = (time.perf_counter() - start) * 1000
        input_tokens, output_tokens = extract_anthropic_usage(response)
        log_claude_api_call(
            model=model,
            duration_ms=duration_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            status="success",
        )
        result = _parse_response(response.content[0].text)
        result.detected_languages = languages
        return result
    except Exception as exc:  # noqa: BLE001 — anthropic/httpx는 다양한 예외를 발생시킬 수 있음  # pylint: disable=broad-exception-caught
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


def _extract_test_score(data: dict) -> int:
    """test_score 추출. 구 포맷(has_tests boolean) 하위 호환."""
    if "test_score" in data:
        return max(0, min(10, int(data["test_score"])))
    return 10 if data.get("has_tests", False) else 0


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
        return AiReviewResult(
            commit_score=max(0, min(AI_RAW_COMMIT_MAX, int(data.get("commit_message_score", AI_DEFAULT_COMMIT_RAW)))),
            ai_score=max(0, min(AI_RAW_DIRECTION_MAX, int(data.get("direction_score", AI_DEFAULT_DIRECTION_RAW)))),
            test_score=_extract_test_score(data),
            summary=str(data.get("summary", "")),
            suggestions=[str(s) for s in data.get("suggestions", [])],
            commit_message_feedback=str(data.get("commit_message_feedback", "")),
            code_quality_feedback=str(data.get("code_quality_feedback", "")),
            security_feedback=str(data.get("security_feedback", "")),
            direction_feedback=str(data.get("direction_feedback", "")),
            test_feedback=str(data.get("test_feedback", "")),
            file_feedbacks=list(data.get("file_feedbacks", [])),
        )
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Failed to parse AI review response: %s", text[:200])
        return _default_result("parse_error")


def _default_result(reason: str = "no_api_key") -> AiReviewResult:
    """API key 없음, 빈 diff, 또는 오류 시 반환하는 중립적 기본값."""
    return AiReviewResult(
        commit_score=17,
        ai_score=17,
        test_score=7,
        summary="AI 리뷰 불가 (기본값 적용)",
        suggestions=[],
        status=reason,
    )
