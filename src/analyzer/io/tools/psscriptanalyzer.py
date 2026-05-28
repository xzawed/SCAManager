"""psscriptanalyzer — PowerShell 정적 분석기.
psscriptanalyzer PowerShell static analyzer.

_PSScriptAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
pwsh 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


class _PSScriptAnalyzer:
    """PSScriptAnalyzer PowerShell 분석기 — JSON 배열 출력 파싱.
    PSScriptAnalyzer PowerShell analyzer — parses JSON array output.
    """

    name = "psscriptanalyzer"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"powershell"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """PowerShell 파일 여부 확인.
        Check whether the file is a PowerShell file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """pwsh 바이너리 설치 여부 확인 (PSScriptAnalyzer는 pwsh를 통해 실행).
        Check whether the pwsh binary is installed (PSScriptAnalyzer runs via pwsh).
        """
        return shutil.which("pwsh") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """Invoke-ScriptAnalyzer ConvertTo-Json 출력을 파싱해 이슈 반환.
        Parse Invoke-ScriptAnalyzer ConvertTo-Json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                [
                    "pwsh", "-NonInteractive", "-Command",
                    f"Invoke-ScriptAnalyzer -Path '{ctx.tmp_path}' "
                    f"-Severity Error,Warning | ConvertTo-Json -AsArray",
                ],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # JSON 배열이 아닌 경우(빈 출력 또는 에러 텍스트) 빈 목록 반환
            # Return empty list for non-JSON-array output (empty or error text)
            if not raw or not raw.startswith("["):
                return []
            data = json.loads(raw)
            issues = []
            for item in data:
                # Severity: 1 또는 "Error" → ERROR, 그 외 → WARNING
                # Severity: 1 or "Error" maps to ERROR, otherwise WARNING
                sev = item.get("Severity")
                severity = Severity.ERROR if sev in (1, "Error") else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="psscriptanalyzer",
                    severity=severity,
                    message=item.get("Message", ""),
                    line=item.get("Line", 0),
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("psscriptanalyzer timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("psscriptanalyzer failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_PSScriptAnalyzer())
