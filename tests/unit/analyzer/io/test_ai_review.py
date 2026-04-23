# tests/test_ai_review.py
import json
from unittest.mock import AsyncMock, MagicMock, patch
from src.analyzer.io.ai_review import (
    AiReviewResult, review_code, _parse_response, _default_result, _extract_test_score
)


async def test_empty_api_key_returns_default():
    result = await review_code("", "feat: test", [("test.py", "+ x = 1")])
    assert isinstance(result, AiReviewResult)
    assert result.commit_score == 17
    assert result.ai_score == 17
    assert result.test_score == 7


async def test_empty_patches_returns_default():
    result = await review_code("sk-key", "feat: test", [])
    assert result.commit_score == 17
    assert result.test_score == 7


def test_parse_response_valid_json():
    text = json.dumps({
        "commit_message_score": 18, "direction_score": 16,
        "test_score": 8, "summary": "Good refactoring",
        "suggestions": ["Add type hints"],
        "commit_message_feedback": "커밋 메시지가 명확합니다",
        "code_quality_feedback": "코드 품질이 우수합니다",
        "security_feedback": "보안 이슈 없음",
        "direction_feedback": "설계 방향이 적절합니다",
        "test_feedback": "테스트가 부분적으로 포함",
        "file_feedbacks": [{"file": "app.py", "issues": ["라인 10: 변수명 개선 필요"]}],
    })
    result = _parse_response(text)
    assert result.commit_score == 18
    assert result.ai_score == 16
    assert result.test_score == 8
    assert result.summary == "Good refactoring"
    assert "Add type hints" in result.suggestions
    assert result.commit_message_feedback == "커밋 메시지가 명확합니다"
    assert result.test_feedback == "테스트가 부분적으로 포함"
    assert len(result.file_feedbacks) == 1


def test_parse_response_clamps_above_max():
    text = '{"commit_message_score": 99, "direction_score": 99, "test_score": 15, "summary": "", "suggestions": []}'
    result = _parse_response(text)
    assert result.commit_score == 20
    assert result.ai_score == 20
    assert result.test_score == 10


def test_parse_response_clamps_below_min():
    text = '{"commit_message_score": -5, "direction_score": -3, "test_score": -1, "summary": "", "suggestions": []}'
    result = _parse_response(text)
    assert result.commit_score == 0
    assert result.ai_score == 0
    assert result.test_score == 0


def test_parse_response_invalid_json_returns_default():
    result = _parse_response("not valid json at all")
    assert result.commit_score == 17
    assert result.test_score == 7


def test_parse_response_json_in_markdown_code_block():
    inner = json.dumps({"commit_message_score": 17, "direction_score": 19,
                        "test_score": 9, "summary": "ok", "suggestions": []})
    text = f"```json\n{inner}\n```"
    result = _parse_response(text)
    assert result.commit_score == 17
    assert result.ai_score == 19
    assert result.test_score == 9


def test_default_result_values():
    result = _default_result()
    assert result.commit_score == 17
    assert result.ai_score == 17
    assert result.test_score == 7
    assert isinstance(result.suggestions, list)
    assert result.commit_message_feedback == ""
    assert result.file_feedbacks == []


def test_parse_response_without_new_fields_uses_defaults():
    """구 포맷(test_score 없음, has_tests boolean)도 정상 파싱되어야 함."""
    text = '{"commit_message_score": 18, "direction_score": 16, "has_tests": true, "summary": "ok", "suggestions": []}'
    result = _parse_response(text)
    assert result.commit_score == 18
    assert result.test_score == 10  # has_tests=true → test_score=10


def test_parse_response_backward_compat_has_tests_false():
    """구 포맷 has_tests=false → test_score=0."""
    text = '{"commit_message_score": 18, "direction_score": 16, "has_tests": false, "summary": "ok", "suggestions": []}'
    result = _parse_response(text)
    assert result.test_score == 0


def test_extract_test_score_prefers_test_score_over_has_tests():
    """test_score가 있으면 has_tests는 무시."""
    data = {"test_score": 7, "has_tests": False}
    assert _extract_test_score(data) == 7


async def test_review_code_calls_anthropic_and_parses():
    mock_response = MagicMock()
    mock_text = json.dumps({"commit_message_score": 18, "direction_score": 17,
                            "test_score": 10, "summary": "ok", "suggestions": []})
    mock_response.content = [MagicMock(text=mock_text)]

    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add feature", [("app.py", "+ x = 1")])

    assert result.commit_score == 18
    assert result.ai_score == 17
    assert result.test_score == 10


async def test_review_code_returns_default_on_api_exception():
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add", [("app.py", "+ x = 1")])

    assert result.commit_score == 17
    assert result.test_score == 7


# ---------------------------------------------------------------------------
# Task 1 — AiReviewResult.status 필드 및 _default_result(reason) 파라미터 테스트
# (Red 단계: AiReviewResult에 status 필드 없음, _default_result에 reason 파라미터 없음)
# ---------------------------------------------------------------------------

def test_default_result_has_no_api_key_status():
    # _default_result("no_api_key") 호출 시 status == "no_api_key" 이어야 한다
    result = _default_result("no_api_key")
    assert result.status == "no_api_key"


def test_default_result_has_api_error_status():
    # _default_result("api_error") 호출 시 status == "api_error" 이어야 한다
    result = _default_result("api_error")
    assert result.status == "api_error"


def test_default_result_has_empty_diff_status():
    # _default_result("empty_diff") 호출 시 status == "empty_diff" 이어야 한다
    result = _default_result("empty_diff")
    assert result.status == "empty_diff"


def test_default_result_has_parse_error_status():
    # _default_result("parse_error") 호출 시 status == "parse_error" 이어야 한다
    result = _default_result("parse_error")
    assert result.status == "parse_error"


async def test_review_code_no_key_returns_no_api_key_status():
    # api_key=""로 호출하면 status == "no_api_key" 이어야 한다
    result = await review_code("", "feat: test", [("test.py", "+ x = 1")])
    assert result.status == "no_api_key"


async def test_review_code_empty_diff_returns_empty_diff_status():
    # diff가 빈 문자열(패치 없음)이면 status == "empty_diff" 이어야 한다
    result = await review_code("sk-key", "feat: test", [])
    assert result.status == "empty_diff"


async def test_review_code_api_error_returns_api_error_status():
    # API 호출 중 예외 발생 시 status == "api_error" 이어야 한다
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("network error"))
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add", [("app.py", "+ x = 1")])

    assert result.status == "api_error"


# ---------------------------------------------------------------------------
# Task 2 (2026-04-23) — _parse_response 견고화
# 실제 프로덕션 분석 #543 에서 "AI 응답 파싱 실패" 경고가 관찰됨.
# Claude 가 종종 (1) preamble + 순수 JSON, (2) 대문자 언어 태그,
# (3) JSON 뒤 trailing text 형태로 응답 — 현재 파서는 이 3가지에서 실패.
# ---------------------------------------------------------------------------

def test_parse_response_preamble_without_code_block():
    """Preamble 텍스트 뒤 순수 JSON (코드 블록 없음) — 가장 흔한 실패 패턴."""
    text = (
        "분석 결과는 다음과 같습니다:\n\n"
        '{"commit_message_score": 18, "direction_score": 15, '
        '"test_score": 8, "summary": "OK", "suggestions": []}'
    )
    result = _parse_response(text)
    assert result.status == "success"
    assert result.commit_score == 18
    assert result.ai_score == 15
    assert result.test_score == 8


def test_parse_response_uppercase_json_language_tag():
    """```JSON (대문자) 코드 블록도 정상 파싱되어야 함."""
    text = (
        "```JSON\n"
        '{"commit_message_score": 17, "direction_score": 19, '
        '"test_score": 9, "summary": "ok", "suggestions": []}\n'
        "```"
    )
    result = _parse_response(text)
    assert result.status == "success"
    assert result.commit_score == 17
    assert result.ai_score == 19


def test_parse_response_trailing_text_after_json():
    """JSON 뒤에 설명 텍스트가 붙는 경우 — 코드 블록 없음."""
    text = (
        '{"commit_message_score": 16, "direction_score": 14, '
        '"test_score": 7, "summary": "ok", "suggestions": []}\n\n'
        "추가 의견: 테스트 커버리지를 더 높여주세요."
    )
    result = _parse_response(text)
    assert result.status == "success"
    assert result.commit_score == 16
    assert result.test_score == 7


def test_parse_response_preamble_with_nested_file_feedbacks():
    """Preamble + 중첩된 file_feedbacks 배열도 정상 파싱되어야 함."""
    text = (
        "다음은 리뷰 결과입니다:\n"
        '{"commit_message_score": 18, "direction_score": 16, '
        '"test_score": 8, "summary": "Good", "suggestions": ["tip1"], '
        '"file_feedbacks": [{"file": "a.py", "issues": ["L10"]}]}'
    )
    result = _parse_response(text)
    assert result.status == "success"
    assert len(result.file_feedbacks) == 1
    assert result.file_feedbacks[0]["file"] == "a.py"


async def test_successful_review_has_success_status():
    # 정상적으로 파싱된 결과는 status == "success" 이어야 한다
    import json as _json
    mock_response = MagicMock()
    mock_text = _json.dumps({
        "commit_message_score": 18, "direction_score": 17,
        "test_score": 10, "summary": "ok", "suggestions": [],
    })
    mock_response.content = [MagicMock(text=mock_text)]

    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add feature", [("app.py", "+ x = 1")])

    assert result.status == "success"
