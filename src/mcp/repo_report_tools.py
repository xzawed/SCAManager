"""Repo 분석 레포트 MCP tool 선언.
MCP tool declarations for repo analysis reports.

이 모듈은 /api/repos/report 및 /api/repos/{name}/report 엔드포인트를
MCP tool로 노출한다. 비즈니스 로직 없음 — API 레이어 래퍼.

This module exposes the repo report API endpoints as MCP tools.
No business logic — pure API wrappers.
"""

# MCP tool 선언 목록 (Anthropic tool use 스키마 준수)
# MCP tool declaration list (follows Anthropic tool use schema)
tools: list[dict] = [
    {
        "name": "list_repo_reports",
        "description": (
            "연결된 모든 Repo의 분석 요약을 반환합니다. "
            "각 Repo의 평균 점수·등급·점수 변화·경고 여부와 "
            "전체 포트폴리오 요약(등급 분포·경고 수)을 포함합니다.\n\n"
            "Returns analysis summary for all connected repositories. "
            "Includes avg_score, grade, score_delta, warning flag per repo "
            "and portfolio-level summary (grade_distribution, warning_count)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "default": 30,
                    "description": "집계 기간 (일). 1~365. 기본값 30. / Aggregation window in days. 1–365. Default 30.",
                }
            },
        },
    },
    {
        "name": "get_repo_report",
        "description": (
            "특정 Repo의 상세 분석 레포트를 반환합니다. "
            "점수 트렌드·이슈 카테고리 분포·AI 코드리뷰 제안·반복 발생 이슈를 포함합니다.\n\n"
            "Returns detailed analysis report for a specific repository. "
            "Includes score trend, category breakdown, AI suggestions, and recurring issues."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_name": {
                    "type": "string",
                    "description": "owner/repo 형식. 예: myorg/backend-api / Format: owner/repo. Example: myorg/backend-api",  # pylint: disable=line-too-long
                },
                "days": {
                    "type": "integer",
                    "default": 30,
                    "description": "집계 기간 (일). 1~365. 기본값 30. / Aggregation window in days. 1–365. Default 30.",
                },
            },
            "required": ["repo_name"],
        },
    },
]
