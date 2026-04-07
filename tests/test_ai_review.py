# tests/test_ai_review.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.analyzer.ai_review import (
    AiReviewResult, review_code, _parse_response, _default_result, _extract_test_score
)


async def test_empty_api_key_returns_default():
    result = await review_code("", "feat: test", [("test.py", "+ x = 1")])
    assert isinstance(result, AiReviewResult)
    assert result.commit_score == 15
    assert result.ai_score == 15
    assert result.test_score == 5


async def test_empty_patches_returns_default():
    result = await review_code("sk-key", "feat: test", [])
    assert result.commit_score == 15
    assert result.test_score == 5


def test_parse_response_valid_json():
    text = '{"commit_message_score": 18, "direction_score": 16, "test_score": 8, "summary": "Good refactoring", "suggestions": ["Add type hints"], "commit_message_feedback": "커밋 메시지가 명확합니다", "code_quality_feedback": "코드 품질이 우수합니다", "security_feedback": "보안 이슈 없음", "direction_feedback": "설계 방향이 적절합니다", "test_feedback": "테스트가 부분적으로 포함", "file_feedbacks": [{"file": "app.py", "issues": ["라인 10: 변수명 개선 필요"]}]}'
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
    assert result.commit_score == 15
    assert result.test_score == 5


def test_parse_response_json_in_markdown_code_block():
    text = '```json\n{"commit_message_score": 17, "direction_score": 19, "test_score": 9, "summary": "ok", "suggestions": []}\n```'
    result = _parse_response(text)
    assert result.commit_score == 17
    assert result.ai_score == 19
    assert result.test_score == 9


def test_default_result_values():
    result = _default_result()
    assert result.commit_score == 15
    assert result.ai_score == 15
    assert result.test_score == 5
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
    mock_response.content = [MagicMock(text='{"commit_message_score": 18, "direction_score": 17, "test_score": 10, "summary": "ok", "suggestions": []}')]

    with patch("src.analyzer.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add feature", [("app.py", "+ x = 1")])

    assert result.commit_score == 18
    assert result.ai_score == 17
    assert result.test_score == 10


async def test_review_code_returns_default_on_api_exception():
    with patch("src.analyzer.ai_review.anthropic.AsyncAnthropic") as mock_cls:
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API error"))
        mock_cls.return_value = mock_client

        result = await review_code("sk-test", "feat: add", [("app.py", "+ x = 1")])

    assert result.commit_score == 15
    assert result.test_score == 5
