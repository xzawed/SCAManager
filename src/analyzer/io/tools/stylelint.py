"""stylelint — CSS/SCSS 정적 분석기.
stylelint CSS/SCSS static analyzer.

_StylelintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
stylelint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


class _StylelintAnalyzer:
    """stylelint CSS/SCSS 분석기 — JSON 배열 출력 파싱.
    stylelint CSS/SCSS analyzer — parses JSON array output.
    """

    name = "stylelint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"css", "scss"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """CSS 또는 SCSS 파일 여부 확인.
        Check whether the file is a CSS or SCSS file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """stylelint 바이너리 설치 여부 확인.
        Check whether the stylelint binary is installed.
        """
        return shutil.which("stylelint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """stylelint --formatter=json 출력을 파싱해 이슈 반환.
        Parse stylelint --formatter=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["stylelint", "--formatter=json", ctx.tmp_path],
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
            for file_result in data:
                for warning in file_result.get("warnings", []):
                    # severity 필드: "error" → ERROR, 그 외 → WARNING
                    # severity field: "error" → ERROR, else → WARNING
                    sev = Severity.ERROR if warning.get("severity") == "error" else Severity.WARNING
                    issues.append(AnalysisIssue(
                        tool="stylelint",
                        severity=sev,
                        message=warning.get("text", ""),
                        line=warning.get("line", 0),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("stylelint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("stylelint failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_StylelintAnalyzer())
