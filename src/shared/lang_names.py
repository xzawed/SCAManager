"""다국어 insight 프롬프트 언어명 매핑 — 단일 출처 상수.

Single-source locale-code → Claude prompt language name mapping.
두 서비스(dashboard_service, repo_insight_service)에서 공유.
Shared by dashboard_service and repo_insight_service.
"""
from __future__ import annotations

# 지원 locale 코드 → Claude 프롬프트 언어명 매핑
# Mapping from supported locale codes to language names used in Claude prompts.
LANG_NAMES: dict[str, str] = {"ko": "Korean", "en": "English", "ja": "Japanese"}
