"""MCP repo_report_tools 스키마 검증 테스트.
Schema validation tests for MCP repo_report_tools.
"""
from src.mcp.repo_report_tools import tools


def test_tool_list_length():
    """tool 선언이 정확히 2개여야 한다."""
    assert len(tools) == 2


def test_tool_names():
    """tool 이름이 규격과 일치해야 한다."""
    names = {t["name"] for t in tools}
    assert "list_repo_reports" in names
    assert "get_repo_report" in names


def test_list_repo_reports_schema():
    """list_repo_reports — days 파라미터 선택 필드."""
    tool = next(t for t in tools if t["name"] == "list_repo_reports")
    assert "description" in tool
    schema = tool["input_schema"]
    assert schema["type"] == "object"
    assert "days" in schema["properties"]
    # days는 required 아님
    assert "required" not in schema or "days" not in schema.get("required", [])


def test_get_repo_report_schema():
    """get_repo_report — repo_name 필수 필드."""
    tool = next(t for t in tools if t["name"] == "get_repo_report")
    assert "description" in tool
    schema = tool["input_schema"]
    assert "repo_name" in schema["properties"]
    assert "repo_name" in schema["required"]


def test_tool_descriptions_non_empty():
    """모든 tool에 description이 있어야 한다."""
    for tool in tools:
        assert tool.get("description", "").strip(), \
            f"{tool['name']} description 없음"
