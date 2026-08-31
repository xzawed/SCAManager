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

from defusedxml import ElementTree as ET  # pylint: disable=import-error

from src.analyzer.io.tools._common import analysis_failed
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
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # 🔴 **성공하면 항상 봉투를 낸다** — 그래서 빈 stderr 가 판별식이다.
            #    CI 실바이너리 실측(cppcheck 2.13.0, #1580 `W2-SHAPE`):
            #      깨끗             exit=0 · stderr `<results …><errors></errors></results>`
            #      구문 오류(발견)   exit=0 · 같은 봉투 + `<error id="syntaxError" …>`
            #      없는 경로(크래시) exit=1 · stderr **0자** · stdout 평문
            #    exit code 는 판별식이 아니다 — 발견도 크래시도 비-0 이 될 수 있다.
            #    깨진 입력은 발견으로 나오므로 이 판별식에 걸리지 않는다(과차단 없음).
            # Measured: a successful run always emits the XML envelope on stderr.
            if not r.stderr.strip():
                raise analysis_failed("cppcheck", ctx, r, "produced no XML on stderr")
            try:
                return _parse_cppcheck_xml(r.stderr, ctx.language)
            except ET.ParseError as exc:
                # 봉투는 있는데 읽을 수 없다 = 미분석이다. `[]` 로 흘리면 그 침묵이
                # «이슈 0건 · 완전» 이 된다 — `c`·`cpp` 는 대체 전담 관측면이 없다.
                # Output we cannot read is unanalyzed, not clean.
                raise analysis_failed(
                    "cppcheck", ctx, r, "produced XML this adapter cannot read") from exc
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("cppcheck timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("cppcheck unavailable for %s: %s", ctx.tmp_path, exc)
            return []


def _parse_cppcheck_xml(xml_text: str, language: str) -> list[AnalysisIssue]:
    """cppcheck XML v2 결과를 AnalysisIssue 목록으로 변환한다.

    subprocess mock 없이 XML 픽스처만으로 검증 가능하도록 분리된 모듈 레벨 함수.
    """
    root = ET.fromstring(xml_text)  # nosec B314 — 로컬 cppcheck 가 생성한 XML
    issues: list[AnalysisIssue] = []
    for err in root.findall(".//error"):
        sev = err.get("severity", "warning")
        severity = Severity.ERROR if sev.lower() == "error" else Severity.WARNING
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
