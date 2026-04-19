"""notifier 모듈 공용 헬퍼 — 이슈 수집·메시지 포매팅·truncate."""
from __future__ import annotations

from src.constants import (
    COMMIT_SHA_DISPLAY_LENGTH,
    NOTIFIER_MAX_ISSUES_SHORT,
    NOTIFIER_MESSAGE_TRUNCATE,
)


def format_ref(commit_sha: str, pr_number: int | None) -> str:
    """PR 번호 또는 단축 커밋 SHA 레퍼런스 문자열을 반환한다."""
    if pr_number:
        return f"PR #{pr_number}"
    return f"커밋 {commit_sha[:COMMIT_SHA_DISPLAY_LENGTH]}"


def get_all_issues(analysis_results: list) -> list:
    """analysis_results에서 모든 AnalysisIssue를 평탄화해 반환한다."""
    return [issue for r in analysis_results for issue in r.issues]


def get_issue_samples(analysis_results: list, max_count: int = NOTIFIER_MAX_ISSUES_SHORT) -> list:
    """분석 결과에서 상위 max_count개 이슈를 반환한다."""
    return get_all_issues(analysis_results)[:max_count]


def truncate_message(text: str, max_length: int, suffix: str = "...") -> str:
    """텍스트를 max_length 이하로 절단하고 suffix를 붙인다."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def truncate_issue_msg(msg: str) -> str:
    """이슈 메시지를 표준 표시 길이(NOTIFIER_MESSAGE_TRUNCATE)로 절단한다."""
    return msg[:NOTIFIER_MESSAGE_TRUNCATE]
