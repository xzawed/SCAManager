"""sqlfluff — SQL 정적 분석기.
sqlfluff SQL static analyzer.

_SqlfluffAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
sqlfluff 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


class _SqlfluffAnalyzer:
    """sqlfluff SQL 분석기 — JSON 출력 파싱.
    sqlfluff SQL analyzer — parses JSON output.
    """

    name = "sqlfluff"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"sql"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """SQL 파일 여부 확인.
        Check whether the file is a SQL file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """sqlfluff 바이너리 설치 여부 확인.
        Check whether the sqlfluff binary is installed.
        """
        return shutil.which("sqlfluff") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """sqlfluff lint --format=json 출력을 파싱해 이슈 반환.
        Parse sqlfluff lint --format=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["sqlfluff", "lint", "--format=json", "--dialect=ansi", ctx.tmp_path],
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
            for file_result in data:
                for v in file_result.get("violations", []):
                    issues.append(AnalysisIssue(
                        tool="sqlfluff",
                        severity=Severity.WARNING,
                        message=f"[{v.get('code', '')}] {v.get('description', '')}",
                        line=v.get("line_no", 0),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("sqlfluff timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("sqlfluff failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_SqlfluffAnalyzer())
