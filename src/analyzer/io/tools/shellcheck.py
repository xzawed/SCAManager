"""ShellCheck static analysis tool — Shell 스크립트 코드 품질 분석.

_ShellCheckAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
shellcheck 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _ShellCheckAnalyzer:
    name = "shellcheck"
    category = Category.CODE_QUALITY

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"shell"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Shell 파일 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """shellcheck 바이너리 설치 여부 확인."""
        return shutil.which("shellcheck") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """shellcheck JSON 출력을 파싱해 이슈 목록 반환."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["shellcheck", "-f", "json", ctx.tmp_path],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            if not r.stdout.strip():
                return []
            data = json.loads(r.stdout)
            issues = []
            for item in data:
                level = item.get("level", "warning")
                severity = Severity.ERROR if level == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="shellcheck",
                    severity=severity,
                    message=item.get("message", ""),
                    line=item.get("line", 0),
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("shellcheck timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("shellcheck failed for %s: %s", ctx.tmp_path, exc)
            return []


def _register_shellcheck_analyzers() -> None:
    register(_ShellCheckAnalyzer())


_register_shellcheck_analyzers()
