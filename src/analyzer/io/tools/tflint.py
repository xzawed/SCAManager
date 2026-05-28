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
                capture_output=True, text=True,
                timeout=STATIC_ANALYSIS_TIMEOUT, check=False,
            )
            raw = r.stdout.strip()
            # JSON 오브젝트가 아닌 경우(빈 출력 등) 빈 목록 반환
            # Return empty list for non-JSON-object output (empty or error text)
            if not raw or not raw.startswith("{"):
                return []
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
            logger.warning("tflint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("tflint failed for %s: %s", ctx.tmp_path, exc)
            return []


register(_TflintAnalyzer())
