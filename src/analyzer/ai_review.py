import json
import logging
import re
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)

MAX_DIFF_CHARS = 8000  # Claude API 토큰 비용 제어


@dataclass
class AiReviewResult:
    commit_score: int        # 0-20: 커밋 메시지 품질
    ai_score: int            # 0-20: 구현 방향성
    has_tests: bool
    summary: str
    suggestions: list[str] = field(default_factory=list)


_PROMPT_TEMPLATE = """\
다음 코드 diff와 커밋 메시지를 분석하고 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

커밋 메시지:
{commit_message}

코드 변경사항:
{diff_text}

다음 JSON만 응답 (추가 텍스트 없이):
{{
  "commit_message_score": <0~20 정수, 컨벤션 준수/명확성/변경범위 일치성>,
  "direction_score": <0~20 정수, 구현 방향성/패턴/설계 적합성>,
  "has_tests": <true/false, 테스트 코드 변경 포함 여부>,
  "summary": "<변경사항 한 줄 요약>",
  "suggestions": ["<개선 제안1>", "<개선 제안2>"]
}}"""


async def review_code(
    api_key: str,
    commit_message: str,
    patches: list[str],
) -> AiReviewResult:
    """Claude API로 코드를 리뷰하고 점수를 반환한다. API key가 없으면 기본값 반환."""
    if not api_key:
        return _default_result()

    diff_text = "\n".join(patches)[:MAX_DIFF_CHARS]
    if not diff_text.strip():
        return _default_result()

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=512,
            messages=[{
                "role": "user",
                "content": _PROMPT_TEMPLATE.format(
                    commit_message=commit_message or "(없음)",
                    diff_text=diff_text,
                ),
            }],
        )
        return _parse_response(response.content[0].text)
    except Exception:
        logger.exception("AI review failed, using default scores")
        return _default_result()


def _parse_response(text: str) -> AiReviewResult:
    try:
        cleaned = text.strip()
        # 마크다운 코드 블록 내 JSON 추출 (앞에 설명 텍스트가 있어도 처리)
        block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if block_match:
            cleaned = block_match.group(1)
        data = json.loads(cleaned)
        return AiReviewResult(
            commit_score=max(0, min(20, int(data.get("commit_message_score", 15)))),
            ai_score=max(0, min(20, int(data.get("direction_score", 15)))),
            has_tests=bool(data.get("has_tests", False)),
            summary=str(data.get("summary", "")),
            suggestions=[str(s) for s in data.get("suggestions", [])],
        )
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Failed to parse AI review response: %s", text[:200])
        return _default_result()


def _default_result() -> AiReviewResult:
    """API key 없음, 빈 diff, 또는 오류 시 반환하는 기본값."""
    return AiReviewResult(
        commit_score=15,
        ai_score=15,
        has_tests=False,
        summary="AI 리뷰 불가 (기본값 적용)",
        suggestions=[],
    )
