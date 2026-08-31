"""psscriptanalyzer — PowerShell 정적 분석기.
psscriptanalyzer PowerShell static analyzer.

_PSScriptAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
pwsh 바이너리 **와** PSScriptAnalyzer 모듈이 둘 다 있어야 is_enabled() 가 True 다 —
모듈은 별도 설치라 pwsh 존재만으로는 능력을 재지 못한다.
"""
from __future__ import annotations

import functools
import json
import logging
import os
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.analyzer.io.tools._common import analysis_failed, empty_output_is_a_crash
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


# 🔴 리스트 리터럴 안에서 문자열을 암묵 연결하지 않는다 — 쉼표를 빠뜨린 것과 구별되지
#    않아 CodeQL `py/implicit-string-concatenation-in-list` 가 발화한다(실측).
# Never implicitly concatenate inside a list literal; it is indistinguishable from a
# missing comma. Bound to a name instead.
_MODULE_PROBE = (
    "Get-Module -ListAvailable -Name PSScriptAnalyzer"
    " | Select-Object -ExpandProperty Name"
)


@functools.lru_cache(maxsize=1)
def psscriptanalyzer_module_available() -> bool:
    """PSScriptAnalyzer **모듈**이 있는지 pwsh 에 프로세스당 한 번만 묻는다.

    🔴 `shutil.which("pwsh")` 는 능력을 재지 못한다 — 모듈은 별도 설치다. 실측: pwsh 는
    있고 모듈은 없는 머신에서 `Invoke-ScriptAnalyzer` 가 exit 1 로 죽었고 stdout 이 비어
    그 결과가 «이슈 0건» 으로 기록됐다. 그 배포의 모든 PowerShell 파일이 만점이 된다.

    능력 부재는 미분석이 아니라 **미제공**이므로 `run()` 의 예외가 아니라 이 게이트가
    걸러야 한다 — 예외로 만들면 모듈 없는 호스트의 모든 PowerShell 파일이 `incomplete`
    가 되어 게이트가 통째로 막힌다(`static.py` 의 `uncovered_language` 축이 담당한다).

    The pwsh binary alone does not imply the capability; the module ships separately.
    """
    try:
        r = subprocess.run(  # nosec B603 B607
            ["pwsh", "-NonInteractive", "-Command", _MODULE_PROBE],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # 탐지 자체가 실패하면 켜지 않는다 — 모르면 끄는 쪽이다.
        # If the probe itself fails, stay disabled rather than guess.
        logger.warning("PSScriptAnalyzer module probe failed: %s", exc)
        return False
    return r.returncode == 0 and bool(r.stdout.strip())


class _PSScriptAnalyzer:
    """PSScriptAnalyzer PowerShell 분석기 — JSON 배열 출력 파싱.
    PSScriptAnalyzer PowerShell analyzer — parses JSON array output.
    """

    name = "psscriptanalyzer"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"powershell"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """PowerShell 파일 여부 확인.
        Check whether the file is a PowerShell file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """pwsh **와** PSScriptAnalyzer 모듈이 둘 다 있어야 켠다.
        Both the pwsh binary and the PSScriptAnalyzer module must be present.
        """
        return shutil.which("pwsh") is not None and psscriptanalyzer_module_available()

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """Invoke-ScriptAnalyzer ConvertTo-Json 출력을 파싱해 이슈 반환.
        Parse Invoke-ScriptAnalyzer ConvertTo-Json output and return issues.
        """
        try:
            # 경로를 환경변수로 전달해 PowerShell 커맨드 문자열 인젝션 방지
            # Pass path via env var to prevent PowerShell command string injection
            env = os.environ.copy()
            env["PSSA_PATH"] = ctx.tmp_path
            r = subprocess.run(  # nosec B603 B607
                [
                    "pwsh", "-NonInteractive", "-Command",
                    "Invoke-ScriptAnalyzer -Path $env:PSSA_PATH -Severity Error,Warning | ConvertTo-Json -AsArray",
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
                env=env,
            )
            raw = r.stdout.strip()
            # 🔴 깨끗한 입력의 출력은 `[]` 가 아니라 **빈 문자열**이다 — 실측:
            #    `@() | ConvertTo-Json -AsArray` 는 $null 을 낸다. 그래서 빈 출력을
            #    미분석으로 보면 정상 PowerShell 파일이 전부 차단된다. 판정은 exit 축이다.
            # A clean file yields EMPTY stdout, not "[]"; the exit-code axis below decides.
            issues = []
            if raw:
                if not raw.startswith("["):
                    raise analysis_failed(
                        "psscriptanalyzer", ctx, r, "did not produce a JSON array")
                for item in json.loads(raw):
                    # Severity: 1 또는 "Error" → ERROR, 그 외 → WARNING
                    # Severity: 1 or "Error" maps to ERROR, otherwise WARNING
                    sev = item.get("Severity")
                    severity = Severity.ERROR if sev in (1, "Error") else Severity.WARNING
                    issues.append(AnalysisIssue(
                        tool="psscriptanalyzer",
                        severity=severity,
                        message=item.get("Message", ""),
                        line=item.get("Line", 0),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            if empty_output_is_a_crash(issues, r):
                # 아무것도 못 읽었는데 비정상 종료 — 실측: PSScriptAnalyzer 모듈이 없는
                # 머신에서 `Invoke-ScriptAnalyzer` 가 exit 1 로 죽고 stdout 이 빈다.
                raise analysis_failed("psscriptanalyzer", ctx, r, "produced no output")
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("psscriptanalyzer timed out for %s", ctx.tmp_path)
            return []
        except json.JSONDecodeError as exc:
            raise analysis_failed(
                "psscriptanalyzer", ctx, r, "produced malformed JSON") from exc
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축이 담당한다.
            logger.warning("psscriptanalyzer unavailable for %s: %s", ctx.tmp_path, exc)
            return []


register(_PSScriptAnalyzer())
