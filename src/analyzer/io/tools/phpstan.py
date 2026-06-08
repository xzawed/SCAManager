"""phpstan — PHP 정적 분석기.
phpstan PHP static analyzer.

_PhpstanAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
phpstan 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


class _PhpstanAnalyzer:
    """phpstan PHP 분석기 — JSON 출력 파싱.
    phpstan PHP analyzer — parses JSON output.
    """

    name = "phpstan"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"php"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """PHP 파일 여부 확인.
        Check whether the file is a PHP file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """phpstan 바이너리 설치 여부 확인.
        Check whether the phpstan binary is installed.
        """
        return shutil.which("phpstan") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """phpstan analyse --error-format=json 출력을 파싱해 이슈 반환.
        Parse phpstan analyse --error-format=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["phpstan", "analyse", "--error-format=json", "--no-progress", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # JSON 객체가 아닌 경우('{' 미시작) 빈 목록 반환
            # Return empty list for non-JSON-object output (not starting with '{')
            if not raw or not raw.startswith("{"):
                return []
            data = json.loads(raw)
            issues = []
            # files 딕셔너리 순회 — 각 파일의 messages 목록 파싱
            # Iterate files dict — parse messages list for each file
            for _path, file_data in data.get("files", {}).items():
                for error in file_data.get("messages", []):
                    issues.append(AnalysisIssue(
                        tool="phpstan",
                        severity=Severity.ERROR,
                        message=error.get("message", ""),
                        line=error.get("line", 0),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("phpstan timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("phpstan failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_PhpstanAnalyzer())
