"""Phase 4 PR-T1 — ai_review.py 에러 경로 + cache_control 동작 단위 테스트.

기존 test_ai_review.py 는 happy path 위주 — 에러 경로를 별도 파일로 분리해
가독성 + 14-에이전트 감사 R1-B 의 "AI review 에러 케이스 부족" 갭 해소.

검증 대상:
  - anthropic API 예외 (timeout / rate-limit / auth / connection) → graceful
  - log_claude_api_call 호출 검증 (status="error" + error_type)
  - prompt cache 토큰 추출 (Phase 1 PR-B caching 후속)
  - response 파싱 fallback (preamble + JSON, malformed)
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("GITHUB_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:test")
os.environ.setdefault("TELEGRAM_CHAT_ID", "-100123456")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-key")
os.environ.setdefault("GITHUB_CLIENT_ID", "test-client-id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("SESSION_SECRET", "test-session-secret-32-chars-long!")

# pylint: disable=wrong-import-position
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.analyzer.io.ai_review import (
    _default_result,
    _extract_json_payload,
    _parse_response,
    review_code,
)


# ──────────────────────────────────────────────────────────────────────────
# anthropic API 예외 경로 — 모든 케이스 graceful "api_error" fallback
# ──────────────────────────────────────────────────────────────────────────


async def test_review_code_handles_httpx_connect_error():
    """httpx.ConnectError 발생 시 _default_result("api_error") 반환."""
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=httpx.ConnectError("DNS lookup failed"),
    )
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.status == "api_error"
    assert result.commit_score == 17
    assert result.ai_score == 17
    assert result.test_score == 7


async def test_review_code_handles_httpx_timeout_error():
    """httpx.TimeoutException → api_error fallback."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=httpx.TimeoutException("read timeout"),
    )
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.status == "api_error"


async def test_review_code_handles_runtime_error():
    """RuntimeError (예: anthropic 내부 정책 거부) → api_error fallback.

    실제 anthropic 예외 클래스(APIError 등)는 SDK 의존성 — 광역 Exception catch
    가 의도적이므로 RuntimeError 로 동작 검증.
    """
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(
        side_effect=RuntimeError("policy denied"),
    )
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.status == "api_error"


async def test_review_code_logs_claude_api_call_with_error_status():
    """예외 발생 시 log_claude_api_call(status='error', error_type=...) 호출 검증."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=httpx.ConnectError("net"))
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as mock_log:
        await review_code("sk-test", "feat: test", [("app.py", "+ x = 1")])
    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["status"] == "error"
    assert kwargs["error_type"] == "ConnectError"
    assert kwargs["input_tokens"] == 0
    assert kwargs["output_tokens"] == 0


async def test_review_code_logs_claude_api_call_with_success_status():
    """정상 응답 시 log_claude_api_call(status='success' + cache token) 호출 검증."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text=json.dumps({
        "commit_message_score": 18, "direction_score": 17, "test_score": 8,
        "summary": "ok", "suggestions": [],
        "commit_message_feedback": "", "code_quality_feedback": "",
        "security_feedback": "", "direction_feedback": "", "test_feedback": "",
        "file_feedbacks": [],
    }))]
    response_obj.usage = MagicMock(
        input_tokens=120, output_tokens=300,
        cache_read_input_tokens=80, cache_creation_input_tokens=0,
    )
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as mock_log:
        result = await review_code("sk-test", "feat: test", [("app.py", "+ x = 1")])
    assert result.status == "success"
    mock_log.assert_called_once()
    kwargs = mock_log.call_args.kwargs
    assert kwargs["status"] == "success"
    assert kwargs["input_tokens"] == 120
    assert kwargs["output_tokens"] == 300
    # Phase 1 PR-B caching 후속 — cache 토큰 전달 검증
    assert kwargs["cache_read_tokens"] == 80
    assert kwargs["cache_creation_tokens"] == 0


async def test_review_code_uses_cache_control_in_system_prompt():
    """Phase 1 PR-B: messages.create 호출에 system=[{cache_control: ephemeral}] 포함 검증."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text='{"summary": "ok"}')]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client):
        await review_code("sk-test", "feat: test", [("app.py", "+ x = 1")])
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert "system" in call_kwargs
    system_blocks = call_kwargs["system"]
    assert isinstance(system_blocks, list)
    assert system_blocks[0]["type"] == "text"
    assert system_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert system_blocks[0]["text"]  # 비어있지 않음


async def test_review_code_propagates_detected_languages():
    """build_review_prompt 가 detected_languages 반환 → result.detected_languages 전달."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text='{"summary": "ok"}')]
    response_obj.usage = MagicMock(input_tokens=10, output_tokens=20)
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch(
             "src.analyzer.io.ai_review.build_review_prompt",
             return_value=("user prompt", ["python", "go"]),
         ):
        result = await review_code(
            "sk-test", "feat: test", [("app.py", "+ x = 1")],
        )
    assert result.detected_languages == ["python", "go"]


async def test_review_code_returns_empty_diff_status_for_empty_patches():
    """patches list 가 비어있을 때 status=empty_diff (build_review_prompt → empty)."""
    result = await review_code("sk-test", "feat: x", [])
    assert result.status == "empty_diff"


async def test_review_code_returns_no_api_key_for_missing_key():
    """api_key 가 빈 문자열일 때 status=no_api_key (empty_diff 보다 우선)."""
    result = await review_code("", "feat: x", [("a.py", "+ x = 1")])
    assert result.status == "no_api_key"


# ──────────────────────────────────────────────────────────────────────────
# _extract_json_payload 응답 파싱 fallback
# ──────────────────────────────────────────────────────────────────────────


def test_extract_json_payload_codeblock_lowercase():
    """```json {...} ``` → JSON 본문만 추출."""
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json_payload(text) == '{"key": "value"}'


def test_extract_json_payload_codeblock_uppercase():
    """대문자 ```JSON 도 case-insensitive 매칭."""
    text = '```JSON\n{"key": "value"}\n```'
    assert _extract_json_payload(text) == '{"key": "value"}'


def test_extract_json_payload_codeblock_no_lang_tag():
    """언어 태그 없는 ``` ``` → 동일 매칭."""
    text = '```\n{"key": "value"}\n```'
    assert _extract_json_payload(text) == '{"key": "value"}'


def test_extract_json_payload_with_preamble_and_trailing_text():
    """JSON 앞뒤 설명 텍스트 → 첫 { ~ 마지막 } 구간 추출."""
    text = (
        "Here is the analysis:\n"
        '{"commit_message_score": 18, "summary": "ok"}\n'
        "End of response."
    )
    extracted = _extract_json_payload(text)
    assert extracted.startswith("{")
    assert extracted.endswith("}")
    assert "commit_message_score" in extracted


def test_extract_json_payload_returns_cleaned_when_no_braces():
    """{ } 없으면 cleaned text 그대로 반환."""
    text = "no JSON here at all"
    assert _extract_json_payload(text) == "no JSON here at all"


# ──────────────────────────────────────────────────────────────────────────
# _parse_response — JSON decode/value/key 에러 모두 parse_error fallback
# ──────────────────────────────────────────────────────────────────────────


def test_parse_response_value_error_returns_default():
    """int(non-numeric) ValueError → status=parse_error."""
    text = '{"commit_message_score": "not-a-number"}'
    result = _parse_response(text)
    assert result.status == "parse_error"
    assert result.commit_score == 17


def test_parse_response_invalid_json_returns_default():
    """완전 깨진 JSON → status=parse_error."""
    result = _parse_response("totally broken {][")
    assert result.status == "parse_error"


def test_parse_response_clamps_out_of_range_scores():
    """commit_message_score=99 → max(0, min(20, 99)) = 20."""
    text = json.dumps({
        "commit_message_score": 99, "direction_score": -5, "test_score": 50,
        "summary": "x",
    })
    result = _parse_response(text)
    assert result.commit_score == 20  # clamped to max
    assert result.ai_score == 0       # clamped to min
    assert result.test_score == 10    # clamped to test max


# ──────────────────────────────────────────────────────────────────────────
# _default_result — status enum 정확성
# ──────────────────────────────────────────────────────────────────────────


def test_default_result_carries_status_field():
    """_default_result(reason) 의 status 필드가 reason 그대로."""
    assert _default_result("api_error").status == "api_error"
    assert _default_result("no_api_key").status == "no_api_key"
    assert _default_result("empty_diff").status == "empty_diff"
    assert _default_result("parse_error").status == "parse_error"


def test_default_result_default_reason_is_no_api_key():
    """기본값 호출 시 status='no_api_key'."""
    assert _default_result().status == "no_api_key"


def test_default_result_neutral_scores():
    """모든 default 결과가 동일한 중립 점수 (commit=17, ai=17, test=7)."""
    for reason in ("no_api_key", "empty_diff", "api_error", "parse_error"):
        result = _default_result(reason)
        assert result.commit_score == 17
        assert result.ai_score == 17
        assert result.test_score == 7
        assert result.summary  # 비어있지 않음
