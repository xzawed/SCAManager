"""Python static analysis tools — pylint, flake8, bandit.

각 클래스는 Analyzer 프로토콜을 구현하며 registry.register()로 등록된다.
"""
from __future__ import annotations

import json
import logging
import subprocess  # nosec B404

from src.analyzer.registry import AnalyzeContext
from src.analyzer.static import AnalysisIssue

logger = logging.getLogger(__name__)


class _PylintAnalyzer:
    name = "pylint"
    category = "code_quality"

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Python 파일 여부 확인."""
        return ctx.language == "python"

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """항상 활성화 (pylint는 pip 의존성으로 항상 설치됨)."""
        return True

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """pylint JSON 출력을 파싱해 AnalysisIssue 목록 반환."""
        disable = (
            "C0114,C0115,C0116,C0301,C0411,"
            "E0401,"
            "R0801,R0902,R0903,R0912,R0913,R0914,R0915,R0917,"
            "W0511,W0613,W0621,W0718"
        )
        if ctx.is_test:
            disable += ",W0611,W0212,C0302,R0401"
        try:
            r = subprocess.run(  # nosec B603 B607
                ["pylint", ctx.tmp_path, "--output-format=json",
                 f"--disable={disable}"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            items = json.loads(r.stdout) if r.stdout.strip().startswith("[") else []
            return [
                AnalysisIssue(
                    tool="pylint",
                    severity="error" if item["type"] in ("error", "fatal") else "warning",
                    message=item["message"],
                    line=item["line"],
                    category=self.category,
                    language=ctx.language,
                )
                for item in items
            ]
        except subprocess.TimeoutExpired:
            logger.warning("pylint timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning("pylint failed for %s: %s", ctx.tmp_path, exc)
            return []


class _Flake8Analyzer:
    name = "flake8"
    category = "code_quality"

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Python 파일 여부 확인."""
        return ctx.language == "python"

    def is_enabled(self, ctx: AnalyzeContext) -> bool:  # pylint: disable=unused-argument
        """항상 활성화 (flake8는 pip 의존성으로 항상 설치됨)."""
        return True

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """flake8 출력을 파싱해 AnalysisIssue 목록 반환."""
        cmd = ["flake8", ctx.tmp_path, "--max-line-length=120",
               "--format=%(row)d:%(col)d: %(text)s"]
        if ctx.is_test:
            cmd.append("--ignore=E302,E402,E128,E127,F401,F841,E305")
        try:
            r = subprocess.run(  # nosec B603 B607
                cmd,
                capture_output=True, text=True, timeout=30, check=False,
            )
            issues = []
            for line in r.stdout.strip().splitlines():
                parts = line.split(":", 2)
                if len(parts) == 3:
                    try:
                        issues.append(AnalysisIssue(
                            tool="flake8",
                            severity="warning",
                            message=parts[2].strip(),
                            line=int(parts[0]),
                            category=self.category,
                            language=ctx.language,
                        ))
                    except ValueError:
                        continue
            return issues
        except subprocess.TimeoutExpired:
            logger.warning("flake8 timed out for %s", ctx.tmp_path)
            return []
        except FileNotFoundError as exc:
            logger.warning("flake8 failed for %s: %s", ctx.tmp_path, exc)
            return []


class _BanditAnalyzer:
    name = "bandit"
    category = "security"

    def supports(self, ctx: AnalyzeContext) -> bool:
        """Python 파일 여부 확인."""
        return ctx.language == "python"

    def is_enabled(self, ctx: AnalyzeContext) -> bool:
        """테스트 파일 제외 (bandit은 프로덕션 코드에만 적용)."""
        return not ctx.is_test

    def run(self, ctx: AnalyzeContext) -> list[AnalysisIssue]:
        """bandit JSON 출력을 파싱해 보안 이슈 목록 반환."""
        try:
            r = subprocess.run(  # nosec B603 B607
                ["bandit", "-f", "json", "-q", ctx.tmp_path],
                capture_output=True, text=True, timeout=30, check=False,
            )
            data = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
            return [
                AnalysisIssue(
                    tool="bandit",
                    severity="error" if item["issue_severity"] == "HIGH" else "warning",
                    message=item["issue_text"],
                    line=item["line_number"],
                    category=self.category,
                    language=ctx.language,
                )
                for item in data.get("results", [])
            ]
        except subprocess.TimeoutExpired:
            logger.warning("bandit timed out for %s", ctx.tmp_path)
            return []
        except (json.JSONDecodeError, FileNotFoundError) as exc:
            logger.warning("bandit failed for %s: %s", ctx.tmp_path, exc)
            return []


# 모듈 로드 시 자동 등록
def _register_python_analyzers() -> None:
    from src.analyzer.registry import register  # noqa: PLC0415
    register(_PylintAnalyzer())
    register(_Flake8Analyzer())
    register(_BanditAnalyzer())


_register_python_analyzers()
