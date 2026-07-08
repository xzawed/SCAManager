"""log_claude_api_call 영속화 wire — record 호출 + DB 에러 fail-safe(no raise).
Cost persistence wire — calls record + swallows DB errors (fail-safe)."""
from unittest.mock import patch

from src.shared.claude_metrics import log_claude_api_call


def test_persists_via_helper():
    with patch("src.shared.claude_metrics._persist_cost") as p:
        log_claude_api_call(model="claude-sonnet-4-6", duration_ms=10, input_tokens=1,
                            output_tokens=1, status="success", repo_id=3)
        assert p.called
        assert p.call_args.kwargs["repo_id"] == 3


def test_persist_failure_is_swallowed():
    # _persist_cost 가 raise 해도 log_claude_api_call 은 예외 미전파(API 흐름 보호).
    with patch("src.shared.claude_metrics._persist_cost", side_effect=RuntimeError("db down")):
        log_claude_api_call(model="m", duration_ms=1, input_tokens=0, output_tokens=0, status="success")
    # 예외 없이 반환 = 통과


def test_user_id_passed():
    with patch("src.shared.claude_metrics._persist_cost") as p:
        log_claude_api_call(model="claude-haiku-4-5", duration_ms=5, input_tokens=0,
                            output_tokens=0, status="success", user_id=7)
        assert p.call_args.kwargs["user_id"] == 7
