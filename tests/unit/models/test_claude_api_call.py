"""ClaudeApiCall ORM — 기본값·nullable FK 검증.
ClaudeApiCall ORM — defaults + nullable FK."""
from src.models.claude_api_call import ClaudeApiCall


def test_defaults_and_nullable_fks():
    row = ClaudeApiCall(model="claude-sonnet-4-6", status="success")
    assert row.repo_id is None and row.user_id is None
    assert row.error_type is None
