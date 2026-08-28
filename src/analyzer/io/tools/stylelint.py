"""stylelint — CSS/SCSS 정적 분석기.
stylelint CSS/SCSS static analyzer.

_StylelintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
stylelint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.analyzer.io.tools._common import analysis_failed
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _StylelintAnalyzer:
    """stylelint CSS/SCSS 분석기 — JSON 배열 출력 파싱.
    stylelint CSS/SCSS analyzer — parses JSON array output.
    """

    name = "stylelint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"css", "scss"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """CSS 또는 SCSS 파일 여부 확인.
        Check whether the file is a CSS or SCSS file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """stylelint 바이너리 설치 여부 확인.
        Check whether the stylelint binary is installed.
        """
        return shutil.which("stylelint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """stylelint --formatter=json 출력을 파싱해 이슈 반환.
        Parse stylelint --formatter=json output and return issues.
        """
        try:
            r = subprocess.run(  # nosec B603 B607
                ["stylelint", "--formatter=json", ctx.tmp_path],
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # 🔴 봉투가 아니면 미분석이다 — stylelint 은 이슈 0건이어도
            #    JSON 배열 봉투를 낸다. 빈 출력은 「깨끗함」이 아니라 「돌지 않았음」이다.
            #    exit code 로는 가를 수 없다 — 린터는 이슈를 찾으면 비-0 으로 끝난다.
            # Non-container stdout means stylelint never analyzed the file; a clean run
            # still emits the JSON array. The exit code cannot tell these apart.
            if not raw.startswith("["):
                raise analysis_failed(
                    "stylelint", ctx, r, "did not produce a JSON array")
            data = json.loads(raw)
            issues = []
            for file_result in data:
                for warning in file_result.get("warnings", []):
                    # severity 필드: "error" → ERROR, 그 외 → WARNING
                    # severity field: "error" → ERROR, else → WARNING
                    sev = Severity.ERROR if warning.get("severity") == "error" else Severity.WARNING
                    issues.append(AnalysisIssue(
                        tool="stylelint",
                        severity=sev,
                        message=warning.get("text", ""),
                        line=warning.get("line", 0),
                        category=Category.CODE_QUALITY,
                        language=ctx.language,
                    ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("stylelint timed out for %s", ctx.tmp_path)
            return []
        except json.JSONDecodeError as exc:
            raise analysis_failed(
                "stylelint", ctx, r, "produced malformed JSON") from exc
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("stylelint unavailable for %s: %s", ctx.tmp_path, exc)
            return []


register(_StylelintAnalyzer())
