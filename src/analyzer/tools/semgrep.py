"""Semgrep static analysis tool — 30+ 언어 baseline 정적분석.

_SemgrepAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
semgrep 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _SemgrepAnalyzer:
    name = "semgrep"
    category = Category.CODE_QUALITY

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({
        # Tier 1
        "python", "javascript", "typescript", "java", "go", "rust",
        "c", "cpp", "csharp", "ruby",
        # Tier 2
        "php", "scala", "kotlin", "swift", "elixir",
        "clojure", "solidity", "shell", "dockerfile",
        # Config / Markup
        "yaml", "html", "terraform",
    })

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Semgrep 지원 언어 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """semgrep 바이너리 설치 여부 확인."""
        return shutil.which("semgrep") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """semgrep auto 룰셋으로 분석 후 이슈 목록 반환."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["semgrep", "scan", "--config=auto", "--json",
                 "--timeout", str(STATIC_ANALYSIS_TIMEOUT), ctx.tmp_path],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            if not r.stdout.strip().startswith("{"):
                return []
            data = json.loads(r.stdout)
            issues = []
            for item in data.get("results", []):
                extra = item.get("extra", {})
                metadata = extra.get("metadata", {})
                raw_severity = extra.get("severity", "WARNING").upper()
                severity = Severity.ERROR if raw_severity == "ERROR" else Severity.WARNING
                category = (
                    Category.SECURITY
                    if metadata.get("category") == "security"
                    else Category.CODE_QUALITY
                )
                issues.append(AnalysisIssue(
                    tool="semgrep",
                    severity=severity,
                    message=extra.get("message", item.get("check_id", "")),
                    line=item.get("start", {}).get("line", 0),
                    category=category,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("semgrep timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning("semgrep failed for %s: %s", ctx.tmp_path, exc)
            return []


def _register_semgrep_analyzers() -> None:
    register(_SemgrepAnalyzer())


_register_semgrep_analyzers()
