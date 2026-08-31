"""ktlint — Kotlin 정적 분석기.
ktlint Kotlin static analyzer.

_KtlintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
ktlint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
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


def json_array_payload(raw: str) -> str:
    """ktlint stdout 에서 **JSON 배열 부분만** 꺼낸다. 없으면 빈 문자열.

    🔴 왜 `startswith("[")` 로는 안 되는가 (2026-08-19 CI 실측, ktlint 1.8.0):
    ktlint 는 JSON 리포터를 써도 **stdout 앞에 로그 줄을 붙인다** —

        14:16:17.124 [main] WARN com.pinterest.ktlint.cli...KtlintCommandLine -- Lint has
        found errors than can be autocorrected...
        [
            { ... "rule": "standard:no-semi" ... }
        ]

    구판은 `raw.startswith("[")` 가 거짓이면 조용히 `[]` 를 반환했다. 즉 **자동수정
    가능한 위반이 있는 모든 Kotlin 파일에서 분석 결과가 0건**이었고, 그것이 「깨끗함」
    으로 보였다. 계약 도구가 살아 있는데 죽은 것과 같았다.

    🔴 `raw.index("[")` 도 안 된다 — 로그 줄 안의 `[main]` 이 먼저 잡힌다.
    JSON 리포터는 배열을 **줄 맨 앞**에서 연다. 그 줄부터 취한다.

    Strip ktlint's log preamble: the JSON reporter still writes WARN lines to stdout, and
    `raw.index("[")` would match `[main]` inside the log. Cut from the first line that
    *starts* with `[`.
    """
    lines = raw.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("["):
            return "\n".join(lines[i:]).strip()
    return ""


class _KtlintAnalyzer:
    """ktlint Kotlin 분석기 — JSON 출력 파싱.
    ktlint Kotlin analyzer — parses JSON output.
    """

    name = "ktlint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"kotlin"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Kotlin 파일 여부 확인.
        Check whether the file is a Kotlin file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """ktlint **와 JVM** 이 모두 있는지 확인.

        🔴 `which("ktlint")` 만으로는 능력을 재지 못한다. `railway.toml` 이 받는 릴리스
        에셋은 네이티브 실행파일이 아니라 **셸 래퍼**다 — 첫 줄이 `#!/bin/sh` 이고 Java
        메이저 버전을 탐지해 내장 JAR 를 실행한다(실측: 에셋 첫 바이트 직접 조회).
        그런데 조달에 java 가 없다(`nixpacks.toml::aptPkgs` · `railway.toml` 둘 다 0건).
        그래서 파일은 있고 실행은 안 되는 상태가 되고, `run()` 이 JSON 배열을 못 얻어
        `[]` 를 돌려주면 **모든 Kotlin 파일이 「이슈 0건 · 완전」** 이 된다.

        🔴 **벽이 아니라 게이트다.** 여기서 False 를 내면 `unavailable_tools` 로 가고,
        ktlint 바이너리 자체는 있으므로 `static.py::def _binary_is_absent` 가 조달 회귀로
        승격하지 않는다 — kotlin 은 `no_dedicated_observer` 로 표면화된다. `run()` 에서
        예외로 올리면 그 대신 모든 `.kt` 가 `incomplete` 가 된다(#1564 가 slither 에서
        낸 사고와 같은 형태).

        Gate on the JVM too: the shipped asset is a /bin/sh wrapper around a JAR and the image
        provisions no java, so presence of the file does not mean the tool can run.
        """
        return (shutil.which("ktlint") is not None
                and shutil.which("java") is not None)

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """ktlint --reporter=json 출력을 파싱해 이슈 반환.
        Parse ktlint --reporter=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["ktlint", "--reporter=json", ctx.tmp_path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            # 🔴 로그 프리앰블을 걷어낸다 — `startswith("[")` 는 ktlint 1.8.0 에서
            #    자동수정 가능한 위반이 있을 때마다 분석을 0건으로 만들었다
            #    (CI 실측 2026-08-19, `json_array_payload` docstring 참조).
            raw = r.stdout.strip()
            payload = json_array_payload(raw)
            if not payload:
                # 🔴 **빈 출력과 「못 읽은 출력」을 가른다** (Grok claim-review `01a01fb3` K2).
                #    둘 다 `[]` 로 떨어지면 관측자에게 **이 버그와 똑같이 보인다** —
                #    분석기가 죽었는지 정말 깨끗한지 구별되지 않는다. 계약 도구가
                #    무언가를 뱉었는데 우리가 못 읽었다면 그건 조용히 넘길 일이 아니다.
                #    (빈 출력은 정상 clean 경로라 로그하지 않는다.)
                # Distinguish empty stdout (genuinely clean) from unparseable stdout:
                # collapsing both to [] reproduces the very silence this fix removed.
                if raw:
                    logger.warning(
                        "ktlint produced output but no JSON array — parser contract broken: %s",
                        raw[:200],
                    )
                return []
            data = json.loads(payload)
            issues = []
            for file_result in data:
                for err in file_result.get("errors", []):
                    issues.append(AnalysisIssue(
                        tool="ktlint",
                        severity=Severity.WARNING,
                        message=f"[{err.get('rule', '')}] {err.get('message', '')}",
                        line=err.get("line", 0),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("ktlint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("ktlint failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_KtlintAnalyzer())
