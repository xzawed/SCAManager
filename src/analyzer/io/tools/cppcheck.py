"""cppcheck static analysis tool — C/C++ 전용 정적분석 (Phase D.1).

_CppCheckAnalyzer 는 Analyzer Protocol 을 구현하며 registry.register() 로
등록된다. cppcheck 바이너리가 없으면 is_enabled() 가 False 를 반환해 조용히
skip 된다. cppcheck 는 XML 결과를 stderr 에 출력하는 관례가 있어 stdout 이
아닌 stderr 를 파싱한다.
"""
from __future__ import annotations

import logging
import shutil
import subprocess  # nosec B404
import xml.etree.ElementTree as ET

from src.analyzer.pure.registry import AnalyzeContext, AnalysisIssue, Category, Severity, register
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _CppCheckAnalyzer:
    name = "cppcheck"
    category = Category.CODE_QUALITY

    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"c", "cpp"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """C/C++ 파일 여부 확인."""
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """cppcheck 바이너리 설치 여부 확인."""
        return shutil.which("cppcheck") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """cppcheck XML 출력을 파싱해 이슈 목록 반환.

        - stderr 가 XML 출력 채널 (cppcheck 관례)
        - --enable=warning,style,performance,portability (information 제외)
        - severity=error 만 error, 나머지(style/performance/portability)는 warning
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                [
                    "cppcheck",
                    "--xml", "--xml-version=2",
                    "--enable=warning,style,performance,portability",
                    "--platform=unix64",
                    "--inline-suppr",
                    "--quiet",
                    ctx.tmp_path,
                ],
                capture_output=True, text=True, timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            if not r.stderr.strip():
                return []
            return _parse_cppcheck_xml(r.stderr, ctx.language)
        except subprocess.TimeoutExpired:
            logger.warning("cppcheck timed out for %s", ctx.tmp_path)
            return []
        except (OSError, ET.ParseError) as exc:
            logger.warning("cppcheck failed for %s: %s", ctx.tmp_path, exc)
            return []


def _parse_cppcheck_xml(xml_text: str, language: str) -> list[AnalysisIssue]:
    """cppcheck XML v2 결과를 AnalysisIssue 목록으로 변환한다.

    subprocess mock 없이 XML 픽스처만으로 검증 가능하도록 분리된 모듈 레벨 함수.
    """
    root = ET.fromstring(xml_text)  # nosec B314 — 로컬 cppcheck 가 생성한 XML
    issues: list[AnalysisIssue] = []
    for err in root.findall(".//error"):
        sev = err.get("severity", "warning")
        severity = Severity.ERROR if sev == "error" else Severity.WARNING
        message = err.get("msg", "") or err.get("verbose", "") or err.get("id", "")
        line = 0
        loc = err.find("location")
        if loc is not None:
            try:
                line = int(loc.get("line", "0"))
            except (TypeError, ValueError):
                line = 0
        issues.append(AnalysisIssue(
            tool="cppcheck",
            severity=severity,
            message=message,
            line=line,
            category=Category.CODE_QUALITY,
            language=language,
        ))
    return issues


def _register_cppcheck_analyzers() -> None:
    register(_CppCheckAnalyzer())


_register_cppcheck_analyzers()
