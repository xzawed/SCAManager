"""dotnet_format — C# 포맷 검사기.
dotnet_format C# formatting checker.

_DotnetFormatAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
dotnet 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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

# dotnet format 진단 출력 패턴: (줄,열): error|warning <code>: 메시지
# Pattern for dotnet format diagnostic output: (line,col): error|warning <code>: message
_DOTNET_DIAG_RE = re.compile(
    r'\((\d+),\d+\):\s+(error|warning)\s+\w+:[ \t]+(\S[^\n]*)$',
    re.MULTILINE,
)


class _DotnetFormatAnalyzer:
    """dotnet format C# 분석기 — stderr/stdout 정규식 파싱.
    dotnet format C# analyzer — parses stderr/stdout via regex.
    """

    name = "dotnet_format"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"csharp"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """C# 파일 여부 확인.
        Check whether the file is a C# file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """🔴 **항상 False** — 이 도구는 단일 `.cs` 파일을 분석할 수 없다 (#1565).

        `dotnet format` 은 **프로젝트/솔루션**을 요구하는데 `static.py` 는 파일 하나를 임시
        디렉터리에 떼어 놓는다. 실측(세 입력 전부): `exit=1 · 이슈 0건 · stderr 749바이트`
        (「유효한 프로젝트 또는 솔루션 파일이 아님」). 즉 **한 번도 동작한 적이 없다.**

        🔴 그런데 `shutil.which("dotnet")` 로 켜 두면 그 무동작이 「돌았다」로 세어져
        `static.py::no_dedicated_observer` 신호를 **지운다**. 실측:

            dotnet 있음   unavailable=[]                no_dedicated=None      ← 「완전 · 깨끗」
            dotnet 없음   unavailable=['dotnet_format'] no_dedicated='csharp'  ← 사실

        **설치돼 있으면 보고가 더 나빠진다.** 그것이 이 도구의 실제 효과였다.

        🔴 임시 `.csproj` 로 감싸도 살아나지 않는다 — 실측(#1586 인코딩 수정 이후):
            full format(proj)     dirty 5건 / clean 0 / **broken 0** · 5.3s
            whitespace --folder   dirty 5건 / clean 0 / **broken 0** · 1.7s
        `broken` 은 문법이 깨졌는데 공백만 정돈된 C# 이다 — 둘 다 「깨끗」으로 본다.
        `dotnet format` 은 **서식 도구이지 분석기가 아니고**, 진단도 `.cs` 가 아니라
        프로젝트/폴더에 귀속돼 줄번호가 소스의 것이 아니다.

        조달: `dotnet` 은 `ci.yml`·`nixpacks.toml`·`railway.toml` 어디에도 없고
        `PROVISIONED_ANALYZERS` 밖이다. 끄면 C# 은 `no_dedicated_observer` 로 기록된다 —
        차단이 아니라 가시화이고, 그것이 오늘의 사실이다.

        Always off: `dotnet format` needs a project, sees only whitespace, and attributes
        diagnostics to the project — keeping it on merely erased the missing-observer signal.
        """
        return False

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """dotnet format --verify-no-changes 출력을 파싱해 이슈 반환.
        Parse dotnet format --verify-no-changes output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["dotnet", "format", "--verify-no-changes", ctx.tmp_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # stderr 우선, 없으면 stdout 사용
            # Prefer stderr; fall back to stdout
            output = r.stderr or r.stdout
            issues = []
            for m in _DOTNET_DIAG_RE.finditer(output):
                line_no = int(m.group(1))
                level = m.group(2)
                message = m.group(3).strip()
                # error → ERROR, warning → WARNING
                severity = Severity.ERROR if level == "error" else Severity.WARNING
                issues.append(AnalysisIssue(
                    tool="dotnet_format",
                    severity=severity,
                    message=message,
                    line=line_no,
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("dotnet_format timed out for %s", ctx.tmp_path)
            return []
        except OSError as exc:
            logger.warning("dotnet_format failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_DotnetFormatAnalyzer())
