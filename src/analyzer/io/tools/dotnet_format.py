"""dotnet_format — C# 포맷 검사기.
dotnet_format C# formatting checker.

_DotnetFormatAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
dotnet 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import logging
import re
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)

# dotnet format 진단 출력 패턴: (줄,열): error|warning <code>: 메시지
# Pattern for dotnet format diagnostic output: (line,col): error|warning <code>: message
_DOTNET_DIAG_RE = re.compile(
    r'\((\d+),\d+\):\s+(error|warning)\s+\w+:[ \t]+(\S[^\n]*)$',
    re.MULTILINE,
)


class _DotnetFormatAnalyzer:
    """dotnet format C# 분석기 — stderr/stdout 정규식 파싱.
    dotnet format C# analyzer — parses stderr/stdout via regex.
    """

    name = "dotnet_format"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"csharp"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """C# 파일 여부 확인.
        Check whether the file is a C# file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """dotnet 바이너리 설치 여부 확인.
        Check whether the dotnet binary is installed.
        """
        return shutil.which("dotnet") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """dotnet format --verify-no-changes 출력을 파싱해 이슈 반환.
        Parse dotnet format --verify-no-changes output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["dotnet", "format", "--verify-no-changes", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # stderr 우선, 없으면 stdout 사용
            # Prefer stderr; fall back to stdout
            output = r.stderr or r.stdout
            issues = []
            for m in _DOTNET_DIAG_RE.finditer(output):
                line_no = int(m.group(1))
                level = m.group(2)
                message = m.group(3).strip()
                # error → ERROR, warning → WARNING
                severity = Severity.ERROR if level == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="dotnet_format",
                    severity=severity,
                    message=message,
                    line=line_no,
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("dotnet_format timed out for %s", ctx.tmp_path)
            return []
        except OSError as exc:
            logger.warning("dotnet_format failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_DotnetFormatAnalyzer())
