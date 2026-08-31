"""tflint — Terraform/HCL 정적 분석기.
tflint Terraform/HCL static analyzer.

_TflintAnalyzer는 Analyzer Protocol을 구현하며 registry.register()로 등록된다.
tflint 바이너리가 없으면 is_enabled()가 False를 반환해 조용히 skip된다.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess  # nosec B404

from src.analyzer.pure.registry import (
    AnalyzeContext, AnalysisIssue, Category, Severity, register,
)
from src.analyzer.io.tools._common import analysis_failed
from src.constants import STATIC_ANALYSIS_TIMEOUT

logger = logging.getLogger(__name__)


class _TflintAnalyzer:
    """tflint Terraform/HCL 분석기 — JSON 출력 파싱.
    tflint Terraform/HCL analyzer — parses JSON output.
    """

    name = "tflint"
    category = Category.CODE_QUALITY
    SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"terraform", "hcl"})

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Terraform/HCL 파일 여부 확인.
        Check whether the file is a Terraform or HCL file.
        """
        return ctx.language in self.SUPPORTED_LANGUAGES

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """tflint 바이너리 설치 여부 확인.
        Check whether the tflint binary is installed.
        """
        return shutil.which("tflint") is not None

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """tflint --format=json 출력을 파싱해 이슈 반환.
        Parse tflint --format=json output and return issues.
        """
        try:
            # tflint은 디렉토리 기준으로 동작 — tmp 파일이 있는 디렉토리를 --chdir로 전달
            # tflint operates on directories — pass the directory containing the tmp file via --chdir
            chdir = os.path.dirname(ctx.tmp_path)
            r = subprocess.run(  # nosec B603 B607
                ["tflint", "--format=json", "--chdir", chdir],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # 🔴 봉투가 아니면 미분석이다 — tflint 은 이슈 0건이어도
            #    JSON 객체 봉투를 낸다. 빈 출력은 「깨끗함」이 아니라 「돌지 않았음」이다.
            #    exit code 로는 가를 수 없다 — 린터는 이슈를 찾으면 비-0 으로 끝난다.
            # Non-container stdout means tflint never analyzed the file; a clean run
            # still emits the JSON object. The exit code cannot tell these apart.
            if not raw.startswith("{"):
                raise analysis_failed(
                    "tflint", ctx, r, "did not produce a JSON object")
            data = json.loads(raw)
            issues = []
            for issue in data.get("issues", []):
                rule_sev = issue.get("rule", {}).get("severity", "warning").lower()
                severity = Severity.ERROR if rule_sev == "error" else Severity.WARNING
                line = issue.get("range", {}).get("start", {}).get("line", 0)
                issues.append(AnalysisIssue(
                    tool="tflint",
                    severity=severity,
                    message=issue.get("message", ""),
                    line=line,
                    category=Category.CODE_QUALITY,
                    language=ctx.language,
                ))
            return issues
        except subprocess.TimeoutExpired:
            ctx.timed_out = True
            logger.warning("tflint timed out for %s", ctx.tmp_path)
            return []
        except json.JSONDecodeError as exc:
            raise analysis_failed(
                "tflint", ctx, r, "produced malformed JSON") from exc
        except FileNotFoundError as exc:
            # which() 통과 뒤 사라진 바이너리 — 조달 축(`unavailable_tools`)이 담당한다.
            # 그 밖의 OSError(깨진 shebang · 권한)는 미분석이므로 올라간다.
            # A binary that vanished after the which() gate; procurement owns it.
            logger.warning("tflint unavailable for %s: %s", ctx.tmp_path, exc)
            return []


register(_TflintAnalyzer())
