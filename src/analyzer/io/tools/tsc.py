"""tsc — TypeScript 타입체크 분석기.
tsc TypeScript type-checker analyzer.

_TscAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
tsc 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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

# tsc 출력 형식: /path/file.ts(LINE,COL): error|warning TSxxxx: message
# tsc output format: /path/file.ts(LINE,COL): error|warning TSxxxx: message
_TSC_DIAG_RE = re.compile(
    r'^[^\n(]+\((\d+),\d+\):\s+(error|warning)\s+TS\d+:[ \t]+(\S[^\n]*)$',
    re.MULTILINE,
)


class _TscAnalyzer:
    """TypeScript 타입체크 분석기 — tsc --noEmit 실행 후 진단 파싱.
    TypeScript type-checker — runs tsc --noEmit and parses diagnostics.
    """

    name = "tsc"
    category = Category.CODE_QUALITY

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"typescript"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """TypeScript 파일 여부 확인.
        Check whether the file is a TypeScript file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """tsc 바이너리 설치 여부 확인.
        Check whether the tsc binary is installed.
        """
        return shutil.which("tsc") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """tsc 진단 출력을 파싱해 AnalysisIssue 목록 반환.
        Parse tsc diagnostic output and return AnalysisIssue list.
        """
        # .tsx 파일은 React JSX 컴파일 플래그 추가
        # Add React JSX compile flag for .tsx files
        jsx_flag = ["--jsx", "react"] if ctx.filename.endswith(".tsx") else []
        try:
            r = subprocess.run(  # nosec B603 B607
                [
                    "tsc", "--noEmit", "--strict", "--skipLibCheck",
                    "--lib", "dom,es2020", "--target", "es2020",
                    "--module", "esnext",
                    "--allowJs",
                ] + jsx_flag + [ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            output = r.stderr or r.stdout
            issues = []
            for m in _TSC_DIAG_RE.finditer(output):
                line_no = int(m.group(1))
                level = m.group(2)
                message = m.group(3).strip()
                severity = Severity.ERROR if level == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="tsc",
                    severity=severity,
                    message=message,
                    line=line_no,
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("tsc timed out for %s", ctx.tmp_path)
            return []
        except OSError as exc:
            logger.warning("tsc failed for %s: %s", ctx.tmp_path, exc)
            return []


def _register_tsc_analyzers() -> None:
    register(_TscAnalyzer())


_register_tsc_analyzers()
