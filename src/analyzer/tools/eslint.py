"""ESLint static analysis tool — JavaScript/TypeScript 코드 품질 분석.

_ESLintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
eslint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec B404

from src.analyzer.registry import AnalyzeContext
from src.analyzer.static import AnalysisIssue

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "configs", "eslint.config.json"
))


class _ESLintAnalyzer:
    name = "eslint"
    category = "code_quality"

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"javascript", "typescript"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        return shutil.which("eslint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        try:
            r = subprocess.run(  # nosec B603 B607
                ["eslint", "--format=json", "--no-eslintrc",
                 "-c", _CONFIG_PATH, ctx.tmp_path],
                capture_output=True, text=True, timeout=30, check=False,
            )
            if not r.stdout.strip().startswith("["):
                return []
            data = json.loads(r.stdout)
            issues = []
            for file_result in data:
                for msg in file_result.get("messages", []):
                    severity = "error" if msg.get("severity", 1) == 2 else "warning"
                    issues.append(AnalysisIssue(
                        tool="eslint",
                        severity=severity,
                        message=msg.get("message", ""),
                        line=msg.get("line", 0),
                        category="code_quality",
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("eslint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("eslint failed for %s: %s", ctx.tmp_path, exc)
            return []


def _register_eslint_analyzers() -> None:
    from src.analyzer.registry import register  # noqa: PLC0415
    register(_ESLintAnalyzer())


_register_eslint_analyzers()
