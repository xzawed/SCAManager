"""swiftlint — Swift 정적 분석기.
swiftlint Swift static analyzer.

_SwiftlintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
swiftlint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _SwiftlintAnalyzer:
    """swiftlint Swift 분석기 — JSON 배열 출력 파싱.
    swiftlint Swift analyzer — parses JSON array output.
    """

    name = "swiftlint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"swift"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Swift 파일 여부 확인.
        Check whether the file is a Swift file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """swiftlint 바이너리 설치 여부 확인.
        Check whether the swiftlint binary is installed.
        """
        return shutil.which("swiftlint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """swiftlint lint --reporter json 출력을 파싱해 이슈 반환.
        Parse swiftlint lint --reporter json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["swiftlint", "lint", "--reporter", "json", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # JSON 배열이 아닌 경우('[' 미시작) 빈 목록 반환
            # Return empty list for non-JSON-array output (not starting with '[')
            if not raw or not raw.startswith("["):
                return []
            data = json.loads(raw)
            issues = []
            for item in data:
                # severity 필드: "error" → ERROR, 그 외 → WARNING
                # severity field: "error" → ERROR, else → WARNING
                sev = Severity.ERROR if item.get("severity") == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="swiftlint",
                    severity=sev,
                    message=item.get("reason", ""),
                    line=item.get("line", 0),
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("swiftlint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("swiftlint failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_SwiftlintAnalyzer())
