"""Analyzer Registry — Protocol + REGISTRY + register().

Usage:
    from src.analyzer.registry import register, REGISTRY, AnalyzeContext

    class MyAnalyzer:
        name = "my-tool"
        category = "code_quality"
        def supports(self, ctx): return ctx.language == "go"
        def is_enabled(self, ctx): return True
        def run(self, ctx): return []

    register(MyAnalyzer())
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from src.analyzer.static import AnalysisIssue

Category = Literal["code_quality", "security"]


@dataclass
class AnalyzeContext:
    """단일 파일 분석에 필요한 모든 컨텍스트."""
    filename: str
    content: str
    language: str       # detect_language() 반환값
    is_test: bool
    tmp_path: str       # 임시 파일 경로 (분석 도구에 전달)
    repo_config: object | None = None


@runtime_checkable
class Analyzer(Protocol):
    """정적 분석 도구가 구현해야 하는 프로토콜."""
    name: str
    category: Category

    def supports(self, ctx: AnalyzeContext) -> bool:
        """이 파일/언어를 분석할 수 있는지 여부."""
        return False  # pragma: no cover

    def is_enabled(self, ctx: AnalyzeContext) -> bool:
        """실행 조건 충족 여부 (도구 설치 여부, is_test 등)."""
        return False  # pragma: no cover

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """분석 실행 후 이슈 목록 반환."""
        return []  # pragma: no cover


REGISTRY: list[Analyzer] = []


def register(analyzer: Analyzer) -> None:
    """Analyzer를 전역 REGISTRY에 등록한다. 동일 name이 이미 있으면 무시한다."""
    if any(a.name == analyzer.name for a in REGISTRY):
        return
    REGISTRY.append(analyzer)
