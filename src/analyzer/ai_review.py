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
    test_score: int          # 0-10: 테스트 커버리지 점수
    summary: str
    suggestions: list[str] = field(default_factory=list)
    commit_message_feedback: str = ""    # 커밋 메시지 평가 상세
    code_quality_feedback: str = ""      # 코드 품질 평가 상세
    security_feedback: str = ""          # 보안 평가 상세
    direction_feedback: str = ""         # 구현 방향성 평가 상세
    test_feedback: str = ""              # 테스트 평가 상세
    file_feedbacks: list[dict] = field(default_factory=list)  # 파일별 피드백


_PROMPT_TEMPLATE = """\
다음 변경사항(코드, 문서, 설정 파일 등)과 커밋 메시지를 분석하고 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

커밋 메시지:
{commit_message}

변경된 파일 목록:
{filenames}

변경사항:
{diff_text}

다음 JSON만 응답 (추가 텍스트 없이):
{{
  "commit_message_score": <0~20 정수, 컨벤션 준수/명확성/변경범위 일치성>,
  "direction_score": <0~20 정수, 구현 방향성/패턴/설계 적합성>,
  "test_score": <0~10 정수, 아래 채점 기준 참고>,
  "summary": "<변경사항 2~3문장 요약: 무엇을 왜 변경했는지>",
  "suggestions": ["<구체적 개선 제안 (파일명:라인 포함)>"],
  "commit_message_feedback": "<커밋 메시지 평가: 컨벤션 준수 여부, 명확성, 변경범위 일치성에 대한 구체적 피드백>",
  "code_quality_feedback": "<코드 품질 평가: 가독성, 네이밍, 중복, 복잡도 등 구체적 피드백>",
  "security_feedback": "<보안 평가: 잠재적 보안 취약점, 입력 검증, 인증 등에 대한 피드백. 이슈 없으면 '보안 이슈 없음'>",
  "direction_feedback": "<구현 방향성 평가: 설계 패턴, 아키텍처 적합성, 확장성에 대한 피드백>",
  "test_feedback": "<테스트 평가: 테스트 존재 여부, 커버리지 충분성, 엣지케이스 포함 여부>",
  "file_feedbacks": [
    {{"file": "<파일명>", "issues": ["<라인 N: 구체적 문제 설명과 수정 방법>"]}}
  ]
}}

test_score 채점 기준:
- 10: 테스트 불필요 파일만 변경됨(.md, .cfg, .toml, .yml, .yaml, .html, .css, .json, .txt, .rst, .ini, Dockerfile, .gitignore, LICENSE 등) 또는 변경에 대한 충분한 테스트 포함
- 7~9: 테스트 코드 존재하나 커버리지가 부분적 (핵심 경로만 커버, 엣지케이스 부족 등)
- 4~6: 테스트 파일 수정이 있으나 새로운 코드에 대한 커버리지 부족
- 1~3: 테스트가 필요하지만 미포함 (단순한 변경이라 심각하지 않음)
- 0: 테스트가 반드시 필요한 코드 변경인데 테스트 전무"""


async def review_code(
    api_key: str,
    commit_message: str,
    patches: list[tuple[str, str]],
) -> AiReviewResult:
    """Claude API로 코드를 리뷰하고 점수를 반환한다. API key가 없으면 기본값 반환."""
    if not api_key:
        return _default_result()

    diff_text = "\n".join(
        f"--- {fname}\n{patch}" for fname, patch in patches
    )[:MAX_DIFF_CHARS]
    filenames = "\n".join(fname for fname, _ in patches)

    if not diff_text.strip():
        return _default_result()

    try:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        response = await client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": _PROMPT_TEMPLATE.format(
                    commit_message=commit_message or "(없음)",
                    filenames=filenames or "(없음)",
                    diff_text=diff_text,
                ),
            }],
        )
        return _parse_response(response.content[0].text)
    except Exception:
        logger.exception("AI review failed, using default scores")
        return _default_result()


def _extract_test_score(data: dict) -> int:
    """test_score 추출. 구 포맷(has_tests boolean) 하위 호환."""
    if "test_score" in data:
        return max(0, min(10, int(data["test_score"])))
    return 10 if data.get("has_tests", False) else 0


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
        return _default_result()


def _default_result() -> AiReviewResult:
    """API key 없음, 빈 diff, 또는 오류 시 반환하는 기본값."""
    return AiReviewResult(
        commit_score=15,
        ai_score=15,
        test_score=5,
        summary="AI 리뷰 불가 (기본값 적용)",
        suggestions=[],
    )
