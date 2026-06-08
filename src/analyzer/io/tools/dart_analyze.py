"""dart_analyze — Dart 정적 분석기.
dart_analyze Dart static analyzer.

_DartAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
dart 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


class _DartAnalyzer:
    """dart analyze Dart 분석기 — JSON 출력 파싱.
    dart analyze Dart analyzer — parses JSON output.
    """

    name = "dart_analyze"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"dart"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Dart 파일 여부 확인.
        Check whether the file is a Dart file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """dart 바이너리 설치 여부 확인.
        Check whether the dart binary is installed.
        """
        return shutil.which("dart") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """dart analyze --format=json 출력을 파싱해 이슈 반환.
        Parse dart analyze --format=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["dart", "analyze", "--format=json", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # JSON 객체가 아닌 경우(빈 출력 또는 에러 텍스트) 빈 목록 반환
            # Return empty list for non-JSON-object output (empty or error text)
            if not raw or not raw.startswith("{"):
                return []
            data = json.loads(raw)
            issues = []
            for diag in data.get("diagnostics", []):
                # severity 값에 따라 ERROR 또는 WARNING 분류
                # Classify as ERROR or WARNING based on severity value
                sev_str = diag.get("severity", "")
                severity = Severity.ERROR if sev_str == "ERROR" else Severity.WARNING
                # 줄 번호는 location.range.start.line (1-based)
                # Line number is in location.range.start.line (1-based)
                location = diag.get("location", {})
                rng = location.get("range", {})
                start = rng.get("start", {})
                line_no = start.get("line", 0)
                issues.append(AnalysisIssue(
                    tool="dart_analyze",
                    severity=severity,
                    message=diag.get("problemMessage", ""),
                    line=line_no,
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("dart_analyze timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("dart_analyze failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_DartAnalyzer())
