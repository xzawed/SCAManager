"""Shared data models for GitHub client and CLI diff collection."""
from dataclasses import dataclass


@dataclass
class ChangedFile:
    """Represents a single file changed in a commit or pull request."""

    filename: str
    content: str
    patch: str
    # 콘텐츠 fetch 가 transient 오류(403 rate-limit/5xx)로 실패했는지 여부.
    # True 면 content='' 가 '미분석'을 의미하므로 파이프라인이 incomplete 로 fail-closed 처리한다
    # (404 삭제 파일·바이너리 decode 실패는 정상 — False).
    # Whether content fetch failed transiently (403 rate-limit/5xx). When True, empty content
    # means 'unanalyzed' so the pipeline marks the analysis incomplete (fail-closed). 404 deletes
    # and binary decode failures are legitimate — False.
    fetch_failed: bool = False
