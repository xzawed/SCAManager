"""C1 Phase 3 T3.2 — review_code repo_id 귀속 스레딩 단위 테스트.

review_code 가 keyword-only `repo_id` 인자를 받아 성공/에러 양 경로의
log_claude_api_call 호출에 그대로 전달하는지 검증한다 (비용 귀속, T3.1 영속화 후속).

Unit tests for review_code's repo_id attribution threading (C1 Phase 3 T3.2).
Verifies the keyword-only `repo_id` argument is forwarded to log_claude_api_call
on both the success and error paths (cost attribution, follow-up to T3.1 persistence).
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.analyzer.io.ai_review import review_code

_PATCHES = [("a.py", "@@ -1 +1 @@\n-x\n+y")]


async def test_review_code_passes_repo_id_to_log_on_error_path():
    """예외 발생 시에도 repo_id 가 log_claude_api_call 에 전달된다 (귀속 유지).
    repo_id is forwarded to log_claude_api_call even on the error path."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=httpx.ConnectError("net"))
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as mock_log:
        await review_code("sk-test", "feat: test", _PATCHES, repo_id=3)

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("repo_id") == 3


async def test_review_code_passes_repo_id_to_log_on_success_path():
    """성공 응답 시에도 repo_id 가 log_claude_api_call 에 전달된다 (귀속 유지).
    repo_id is forwarded to log_claude_api_call on the success path too."""
    response_obj = MagicMock()
    response_obj.content = [MagicMock(text=json.dumps({
        "commit_message_score": 18, "direction_score": 17, "test_score": 8,
        "summary": "ok", "suggestions": [],
        "commit_message_feedback": "", "code_quality_feedback": "",
        "security_feedback": "", "direction_feedback": "", "test_feedback": "",
    }))]
    response_obj.usage = MagicMock(
        input_tokens=120, output_tokens=300,
        cache_read_input_tokens=0, cache_creation_input_tokens=0,
    )
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response_obj)
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as mock_log:
        result = await review_code("sk-test", "feat: test", _PATCHES, repo_id=7)

    assert result.status == "success"
    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("repo_id") == 7


async def test_review_code_defaults_repo_id_to_none():
    """repo_id 미전달(CLI 호출 등) 시 log_claude_api_call 에 None 이 전달된다 (회귀 가드).
    Without an explicit repo_id (e.g. CLI callers), log_claude_api_call receives None
    (regression guard for existing callers)."""
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(side_effect=httpx.ConnectError("net"))
    with patch("src.analyzer.io.ai_review.anthropic.AsyncAnthropic", return_value=fake_client), \
         patch("src.analyzer.io.ai_review.log_claude_api_call") as mock_log:
        await review_code("sk-test", "feat: test", _PATCHES)

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs.get("repo_id") is None
