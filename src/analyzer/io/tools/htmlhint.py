"""htmlhint — HTML 정적 분석기.
htmlhint HTML static analyzer.

_HtmlhintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
htmlhint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


class _HtmlhintAnalyzer:
    """htmlhint HTML 분석기 — JSON 배열 출력 파싱.
    htmlhint HTML analyzer — parses JSON array output.
    """

    name = "htmlhint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"html"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """HTML 파일 여부 확인.
        Check whether the file is an HTML file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """htmlhint 바이너리 설치 여부 확인.
        Check whether the htmlhint binary is installed.
        """
        return shutil.which("htmlhint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """htmlhint --format=json 출력을 파싱해 이슈 반환.
        Parse htmlhint --format=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["htmlhint", "--format=json", ctx.tmp_path],
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
                for msg in file_result.get("messages", []):
                    # type 필드: "error" → ERROR, 그 외 → WARNING
                    # type field: "error" → ERROR, else → WARNING
                    sev = Severity.ERROR if msg.get("type") == "error" else Severity.WARNING
                    issues.append(AnalysisIssue(
                        tool="htmlhint",
                        severity=sev,
                        message=msg.get("message", ""),
                        line=msg.get("line", 0),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("htmlhint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("htmlhint failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_HtmlhintAnalyzer())
